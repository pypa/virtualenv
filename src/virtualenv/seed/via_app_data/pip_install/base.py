from __future__ import absolute_import, unicode_literals

import logging
import os
import re
import zipfile
from abc import ABCMeta, abstractmethod
from contextlib import contextmanager
from tempfile import mkdtemp
from threading import Lock

# noinspection PyProtectedMember
from distlib.scripts import ScriptMaker, _enquote_executable
from six import PY3, add_metaclass

from virtualenv.util import ConfigParser
from virtualenv.util.path import Path, safe_delete
from virtualenv.util.six import ensure_text


@add_metaclass(ABCMeta)
class PipInstall(object):
    lock = Lock()

    def __init__(self, wheel, creator, image_folder):
        self._wheel = wheel
        self._creator = creator
        self._image_dir = image_folder
        self._extracted = False
        self.__dist_info = None
        self._console_entry_points = None

    @abstractmethod
    def _sync(self, src, dst):
        raise NotImplementedError

    def install(self, version_info):
        self._extracted = True
        # sync image
        for filename in self._image_dir.iterdir():
            into = self._creator.purelib / filename.name
            if into.exists():
                if into.is_dir() and not into.is_symlink():
                    safe_delete(into)
                else:
                    into.unlink()
            self._sync(filename, into)
        # generate console executables
        consoles = set()
        script_dir = self._creator.script_dir
        for name, module in self._console_scripts.items():
            consoles.update(self._create_console_entry_point(name, module, script_dir, version_info))
        logging.debug("generated console scripts %s", " ".join(i.name for i in consoles))

    def build_image(self):
        # 1. first extract the wheel
        logging.debug("build install image to %s of %s", self._image_dir, self._wheel.name)
        with zipfile.ZipFile(str(self._wheel)) as zip_ref:
            zip_ref.extractall(str(self._image_dir))
            self._extracted = True
        # 2. now add additional files not present in the package
        new_files = self._generate_new_files()
        # 3. finally fix the records file
        self._fix_records(new_files)

    def _records_text(self, files):
        record_data = "\n".join(
            "{},,".format(os.path.relpath(ensure_text(str(rec)), ensure_text(str(self._image_dir)))) for rec in files
        )
        return record_data

    def _generate_new_files(self):
        new_files = set()
        installer = self._dist_info / "INSTALLER"
        installer.write_text("pip\n")
        new_files.add(installer)
        # inject a no-op root element, as workaround for bug in https://github.com/pypa/pip/issues/7226
        marker = self._image_dir / "{}.virtualenv".format(self._dist_info.stem)
        marker.write_text("")
        new_files.add(marker)
        folder = mkdtemp()
        try:
            to_folder = Path(folder)
            rel = os.path.relpath(ensure_text(str(self._creator.script_dir)), ensure_text(str(self._creator.purelib)))
            version_info = self._creator.interpreter.version_info
            for name, module in self._console_scripts.items():
                new_files.update(
                    Path(os.path.normpath(ensure_text(str(self._image_dir / rel / i.name))))
                    for i in self._create_console_entry_point(name, module, to_folder, version_info)
                )
        finally:
            safe_delete(folder)
        return new_files

    @property
    def _dist_info(self):
        if self._extracted is False:
            return None  # pragma: no cover
        if self.__dist_info is None:
            for filename in self._image_dir.iterdir():
                if filename.suffix == ".dist-info":
                    self.__dist_info = filename
                    break
            else:
                raise RuntimeError("no dist info")  # pragma: no cover
        return self.__dist_info

    @abstractmethod
    def _fix_records(self, extra_record_data):
        raise NotImplementedError

    @property
    def _console_scripts(self):
        if self._extracted is False:
            return None  # pragma: no cover
        if self._console_entry_points is None:
            self._console_entry_points = {}
            entry_points = self._dist_info / "entry_points.txt"
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

    def _create_console_entry_point(self, name, value, to_folder, version_info):
        result = []
        maker = ScriptMaker(None, str(to_folder))
        maker.clobber = True  # overwrite
        maker.variants = {""}  # set within patch_distlib_correct_variants
        maker.set_mode = True  # ensure they are executable
        # calling private until https://bitbucket.org/pypa/distlib/issues/135/expose-_enquote_executable-as-public
        maker.executable = _enquote_executable(str(self._creator.exe))
        specification = "{} = {}".format(name, value)
        with self.patch_distlib_correct_variants(version_info, maker):
            new_files = maker.make(specification)
        result.extend(Path(i) for i in new_files)
        return result

    @contextmanager
    def patch_distlib_correct_variants(self, version_info, maker):
        """
        Patch until upstream distutils supports creating scripts with different python target
        https://bitbucket.org/pypa/distlib/issues/134/allow-specifying-the-version-information
        """

        def _write_script(scriptnames, shebang, script, filenames, ext):
            name = next(iter(scriptnames))
            scriptnames = {  # add our variants '', 'X', '-X.Y'
                name,
                "{}{}".format(name, version_info.major),
                "{}-{}.{}".format(name, version_info.major, version_info.minor),
            }
            return previous(scriptnames, shebang, script, filenames, ext)

        previous = maker._write_script
        with self.lock:
            maker._write_script = _write_script
            try:
                yield
            finally:
                maker._write_script = previous

    def clear(self):
        if self._image_dir.exists():
            safe_delete(self._image_dir)

    def has_image(self):
        return self._image_dir.exists() and next(self._image_dir.iterdir()) is not None
