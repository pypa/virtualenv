"""Bootstrap"""
from __future__ import absolute_import, unicode_literals

import logging
import os
import sys
from contextlib import contextmanager
from operator import attrgetter
from shutil import copy2

import six

from virtualenv.info import IS_ZIPAPP
from virtualenv.util.path import Path
from virtualenv.util.six import ensure_str
from virtualenv.util.subprocess import Popen, subprocess
from virtualenv.util.zipapp import ensure_file_on_disk

from . import BUNDLE_SUPPORT, MAX
from .util import Wheel

BUNDLE_FOLDER = Path(os.path.abspath(__file__)).parent


class Version:
    #: the version bundled with virtualenv
    bundle = "bundle"
    #: custom version handlers
    non_version = (bundle,)

    @staticmethod
    def of_version(value):
        return None if value in Version.non_version else value

    @staticmethod
    def as_pip_req(distribution, version):
        return "{}{}".format(distribution, "" if version is None else "=={}".format(version))


def get_wheel(distribution, version, for_py_version, search_dirs, download, cache_dir, app_data):
    """
    Get a wheel with the given distribution-version-for_py_version trio, by using the extra search dir + download
    """
    # not all wheels are compatible with all python versions, so we need to py version qualify it
    of_version = Version.of_version(version)  # remove special placeholder version numbers
    # 1. acquire from embed
    wheel = from_bundle(distribution, of_version, for_py_version, cache_dir)

    # 2. acquire from extra search dir
    found_wheel = from_dir(distribution, of_version, for_py_version, cache_dir, search_dirs)
    if found_wheel is not None and (wheel is None or found_wheel.version_tuple >= wheel.version_tuple):
        wheel = found_wheel

    # 3. download from the internet
    if download:
        download_wheel(distribution, of_version, for_py_version, cache_dir, app_data)
        wheel = _get_wheels(cache_dir, distribution, of_version)[0]  # get latest from cache post download

    return wheel


def from_bundle(distribution, version, for_py_version, wheel_cache_dir):
    """
    Load the bundled wheel to a cache directory.
    """
    bundle = get_bundled_wheel(distribution, for_py_version)
    if bundle is None:
        return None
    if version is None or version == bundle.version:
        bundled_wheel_file = wheel_cache_dir / bundle.path.name
        if not bundled_wheel_file.exists():
            logging.debug("materialize bundled wheel %s to %s", bundle, bundled_wheel_file)
            if IS_ZIPAPP:
                from virtualenv.util.zipapp import extract

                extract(bundle, bundled_wheel_file)
            else:
                copy2(str(bundle), str(bundled_wheel_file))
        return Wheel(bundled_wheel_file)


def get_bundled_wheel(distribution, for_py_version):
    path = BUNDLE_FOLDER / (BUNDLE_SUPPORT.get(for_py_version, {}) or BUNDLE_SUPPORT[MAX]).get(distribution)
    if path is None:
        return None
    return Wheel.from_path(path)


def from_dir(distribution, version, for_py_version, cache_dir, directories):
    """
    Load a compatible wheel from a given folder.
    """
    for folder in directories:
        for wheel in _get_wheels(folder, distribution, version):
            dest = cache_dir / wheel.name
            if wheel.support_py(for_py_version):
                logging.debug("copy extra search dir wheel %s to %s", wheel.path, dest)
                if not dest.exists():
                    copy2(str(wheel.path), str(dest))
                return Wheel(dest)
    return None


def _get_wheels(from_folder, distribution, version):
    wheels = []
    for filename in from_folder.iterdir():
        wheel = Wheel.from_path(filename)
        if wheel and wheel.distribution == distribution:
            if version is None or wheel.version == version:
                wheels.append(wheel)
    return sorted(wheels, key=attrgetter("version_tuple", "distribution"), reverse=True)


def download_wheel(distribution, version, for_py_version, to_folder, app_data):
    to_download = Version.as_pip_req(distribution, version)
    logging.debug("download wheel %s", to_download)
    cmd = [
        sys.executable,
        "-m",
        "pip",
        "download",
        "--disable-pip-version-check",
        "--only-binary=:all:",
        "--no-deps",
        "--python-version",
        for_py_version,
        "-d",
        str(to_folder),
        to_download,
    ]
    # pip has no interface in python - must be a new sub-process
    with pip_wheel_env_run("{}.{}".format(*sys.version_info[0:2]), app_data) as env:
        process = Popen(cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        out, err = process.communicate()
        if process.returncode != 0:
            kwargs = {"output": out}
            if six.PY2:
                kwargs["output"] += err
            else:
                kwargs["stderr"] = err
            raise subprocess.CalledProcessError(process.returncode, cmd, **kwargs)


@contextmanager
def pip_wheel_env_run(version, app_data):
    env = os.environ.copy()
    env.update(
        {
            ensure_str(k): str(v)  # python 2 requires these to be string only (non-unicode)
            for k, v in {"PIP_USE_WHEEL": "1", "PIP_USER": "0", "PIP_NO_INPUT": "1"}.items()
        },
    )
    with ensure_file_on_disk(get_bundled_wheel("pip", version).path, app_data) as pip_wheel_path:
        # put the bundled wheel onto the path, and use it to do the bootstrap operation
        env[str("PYTHONPATH")] = str(pip_wheel_path)
        yield env
