from __future__ import absolute_import, unicode_literals

import logging
import os
import re
import shutil
import zipfile
from abc import ABCMeta, abstractmethod
from stat import S_IREAD, S_IRGRP, S_IROTH, S_IWUSR
from tempfile import mkdtemp
from textwrap import dedent

import six
from six import PY3

from virtualenv.info import IS_WIN
from virtualenv.util import ConfigParser
from virtualenv.util.path import Path


@six.add_metaclass(ABCMeta)
class PipInstall(object):
    def __init__(self, wheel, creator, image_folder):
        self.wheel = wheel
        self.creator = creator
        self.image_folder = image_folder
        self._extracted = False
        self._dist_info = None
        self._console_entry_points = None

    @abstractmethod
    def sync(self, src, dst):
        raise NotImplementedError

    def install(self):
        self._extracted = True
        # sync image
        site_package = self.creator.site_packages[0]
        for filename in self.image_folder.iterdir():
            into = site_package / filename.name
            logging.debug("link %s of %s", filename, into)
            if into.exists():
                if into.is_dir() and not into.is_symlink():
                    shutil.rmtree(str(into))
                else:
                    into.unlink()
            self.sync(filename, into)
        # generate console executables
        consoles = set()
        bin_dir = self.creator.bin_dir
        for name, module in self.console_scripts.items():
            consoles.update(self.create_console_entry_point(name, module, bin_dir))
        logging.debug("generated console scripts %s", " ".join(i.name for i in consoles))

    def build_image(self):
        # 1. first extract the wheel
        logging.debug("build install image to %s of %s", self.image_folder, self.wheel.name)
        with zipfile.ZipFile(str(self.wheel)) as zip_ref:
            zip_ref.extractall(str(self.image_folder))
            self._extracted = True
        # 2. now add additional files not present in the package
        new_files = self._generate_new_files()
        # 3. finally fix the records file
        self._fix_records(new_files)
        # protect the image by making it read only
        self.protect_image()

    def _records_text(self, files):
        record_data = "\n".join(
            "{},,".format(os.path.relpath(six.ensure_text(str(rec)), six.ensure_text(str(self.image_folder))))
            for rec in files
        )
        return record_data

    def protect_image(self):
        self._set_tree(self.image_folder, S_IREAD | S_IRGRP | S_IROTH)

    def free_image(self):
        self._set_tree(self.image_folder, S_IWUSR)

    @staticmethod
    def _set_tree(folder, stat):
        for root, _, files in os.walk(six.ensure_text(str(folder))):
            for filename in files:
                os.chmod(os.path.join(root, filename), stat)

    def _generate_new_files(self):
        new_files = set()
        installer = self.dist_info / "INSTALLER"
        installer.write_text("pip\n")
        new_files.add(installer)
        # inject a no-op root element, as workaround for bug added
        # by https://github.com/pypa/pip/commit/c7ae06c79#r35523722
        marker = self.image_folder / "{}.virtualenv".format(self.dist_info.name)
        marker.write_text("")
        new_files.add(marker)
        folder = mkdtemp()
        try:
            to_folder = Path(folder)
            rel = os.path.relpath(
                six.ensure_text(str(self.creator.bin_dir)), six.ensure_text(str(self.creator.site_packages[0]))
            )
            for name, module in self.console_scripts.items():
                new_files.update(
                    self.image_folder / rel / i.name for i in self.create_console_entry_point(name, module, to_folder)
                )
        finally:
            shutil.rmtree(folder, ignore_errors=True)
        return new_files

    @property
    def dist_info(self):
        if self._extracted is False:
            return None
        if self._dist_info is None:
            for filename in self.image_folder.iterdir():
                if filename.suffix == ".dist-info":
                    self._dist_info = filename
                    break
            else:
                raise RuntimeError("no dist info")
        return self._dist_info

    @abstractmethod
    def _fix_records(self, extra_record_data):
        raise NotImplementedError

    @property
    def console_scripts(self):
        if self._extracted is False:
            return None
        if self._console_entry_points is None:
            self._console_entry_points = {}
            entry_points = self.dist_info / "entry_points.txt"
            if entry_points.exists():
                parser = ConfigParser.ConfigParser()
                with entry_points.open() as file_handler:
                    reader = getattr(parser, "read_file" if PY3 else "readfp")
                    reader(file_handler)
                if "console_scripts" in parser.sections():
                    for name, value in parser.items("console_scripts"):
                        match = re.match(r"(.*?)-?\d\.?\d*", name)
                        if match:
                            name = match.groups(1)[0]
                        self._console_entry_points[name] = value
        return self._console_entry_points

    def create_console_entry_point(self, name, value, to_folder):
        result = []
        if IS_WIN:
            # windows doesn't support simple script files, so fallback to more complicated exe generator
            from distlib.scripts import ScriptMaker

            maker = ScriptMaker(None, str(to_folder))
            maker.clobber = True  # overwrite
            maker.variants = {"", "X", "X.Y"}  # create all variants
            maker.set_mode = True  # ensure they are executable
            maker.executable = str(self.creator.exe)
            specification = "{} = {}".format(name, value)
            new_files = maker.make(specification)
            result.extend(new_files)
        else:
            module, func = value.split(":")
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
                .format(self.creator.exe, module, func)
            )

            version = self.creator.interpreter.version_info
            for new_name in (
                name,
                "{}{}".format(name, version.major),
                "{}-{}.{}".format(name, version.major, version.minor),
            ):
                exe = to_folder / new_name
                exe.write_text(content, encoding="utf-8")
                exe.chmod(0o755)
                result.append(exe)
        return result
