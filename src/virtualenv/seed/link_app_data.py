"""Bootstrap"""
from __future__ import absolute_import, unicode_literals

import logging
import os
import re
import shutil
import sys
import zipfile
from shutil import copytree
from textwrap import dedent

from pathlib2 import Path
from six import PY3

from virtualenv.info import get_default_data_dir

from .wheels.acquire import get_wheel

try:
    import ConfigParser
except ImportError:
    # noinspection PyPep8Naming
    import configparser as ConfigParser


def bootstrap(creator):
    cache = get_default_data_dir() / "seed-v1"
    name_to_whl = get_wheel(creator, cache)
    pip_install(name_to_whl, creator, cache)


def pip_install(wheels, creator, cache):
    site_package, bin_dir, env_exe = creator.site_packages[0], creator.bin_dir, creator.env_exe
    folder_link_method, folder_linked = link_folder()
    for name, wheel in wheels.items():
        logging.debug("install %s from wheel %s", name, wheel)
        extracted = _get_extracted(cache, wheel)
        added, dist_info = _link_content(folder_link_method, site_package, extracted)
        extra_files = _generate_extra_files(bin_dir, env_exe, site_package, dist_info, creator)
        fix_records(creator, dist_info, site_package, folder_linked, added, extra_files)


def link_folder():
    if sys.platform == "win32":
        # on Windows symlinks are unreliable, but we have junctions for folders
        if sys.version_info[0:2] > (3, 4):
            import _winapi  # python3.5 has builtin implementation for junctions

            return _winapi.CreateJunction, True
    else:
        # on POSIX prefer symlinks, however symlink support requires pip 19.3+, not supported by pip
        if sys.version_info[0:2] != (3, 4):
            return os.symlink, True

    # if nothing better fallback to copy the tree
    return copytree, False


def _get_extracted(cache, wheel):
    install_image = cache / "extract"
    install_image.mkdir(parents=True, exist_ok=True)
    extracted = install_image / wheel.name
    if not extracted.exists():
        logging.debug("create install image to %s of %s", extracted, wheel)
        extracted.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(str(wheel)) as zip_ref:
            zip_ref.extractall(str(extracted))
    else:
        logging.debug("install from extract %s", extracted)
    return extracted


def _link_content(folder_link, site_package, extracted):
    added = []
    dist_info = None

    for filename in extracted.iterdir():
        into = site_package / filename.name
        if into.exists():
            if into.is_dir() and not into.is_symlink():
                shutil.rmtree(str(into))
            else:
                into.unlink()
        is_dir = filename.is_dir()
        method = folder_link if is_dir else os.link
        method(str(filename), str(into))
        added.append((is_dir, into))
        if filename.suffix == ".dist-info":
            dist_info = into
    return added, dist_info


def _generate_extra_files(bin_dir, env_exe, site_package, dist_info, creator):
    extra = []
    # pretend was installed by pip
    installer = dist_info / "INSTALLER"
    installer.write_text("pip\n")
    extra.append(installer)

    # inject a no-op root element, as workaround for bug added by https://github.com/pypa/pip/commit/c7ae06c79#r35523722
    marker = site_package / "{}.virtualenv".format(dist_info.name)
    marker.write_text("")
    extra.append(marker)

    console_scripts = load_console_scripts(bin_dir, dist_info, creator)
    for exe, (module, func) in console_scripts.items():
        write_entry_point(env_exe, exe, func, module)
        extra.append(exe)
    return extra


def load_console_scripts(bin_dir, dist_info, creator):
    result = {}
    entry_points = dist_info / "entry_points.txt"
    if entry_points.exists():
        parser = ConfigParser.ConfigParser()
        with entry_points.open() as file_handler:
            reader = getattr(parser, "read_file" if PY3 else "readfp")
            reader(file_handler)
        if "console_scripts" in parser.sections():
            for name, value in parser.items("console_scripts"):
                match = re.match(r"([a-zA-Z]+)([0-9.]*)", name)
                if match:
                    name, version = match.groups()
                    if version is not None:
                        name += ".".join(str(i) for i in creator.interpreter.version_info[0 : len(version.split("."))])
                exe = bin_dir / "{}{}".format(name, ".exe" if sys.platform == "win32" else "")
                module, func = value.split(":")
                result[exe] = module, func
    return result


def write_entry_point(env_exe, exe, func, module):
    content = (
        dedent(
            """
    #!{0}
    # -*- coding: utf-8 -*-
    import re
    import sys

    from {1} import {2}

    if __name__ == "__main__":
        sys.argv[0] = re.sub(r"(-script.pyw?|.exe)?$", "", sys.argv[0])
        sys.exit({2}())
    """
        )
        .lstrip()
        .format(env_exe, module, func)
    )
    exe.write_text(content)
    exe.chmod(0o755)


def fix_records(creator, dist_info, site_package, folder_linked, added, extra_files):
    extra_records = []
    version = creator.interpreter.version_info
    py_c_ext = ".{}-{}{}.pyc".format(creator.interpreter.implementation.lower(), version.major, version.minor)

    def _handle_file(of, base):
        if of.suffix == ".py":
            pyc = base / "{}{}".format(of.stem, py_c_ext)
            extra_records.append(pyc)

    for is_dir, file in added:
        if is_dir:
            if folder_linked:
                extra_records.append(file)
            else:
                for root, _, filenames in os.walk(str(file)):
                    root_path = Path(root) / "__pycache__"
                    for filename in filenames:
                        _handle_file(Path(filename), root_path)
        else:
            root_path = file.parent / "__pycache__"
            _handle_file(file, root_path)
            extra_records.append(file)

    extra_records.extend(extra_files)
    new_records = []
    for rec in extra_records:
        name = os.path.relpath(str(rec), str(site_package))
        new_records.append("{},,".format(name))

    record = dist_info / "RECORD"
    content = ("" if folder_linked else record.read_text()) + "\n".join(new_records)
    record.write_text(content)


def add_record_line(name):
    return "{},,".format(name)
