from __future__ import absolute_import, unicode_literals

import os
import shutil
import subprocess
from stat import S_IREAD, S_IRGRP, S_IROTH, S_IWUSR

import six

from virtualenv.util.subprocess import Popen

from .base import PipInstall


class SymlinkPipInstall(PipInstall):
    def _sync(self, src, dst):
        src_str = six.ensure_text(str(src))
        dest_str = six.ensure_text(str(dst))
        os.symlink(src_str, dest_str)

    def _generate_new_files(self):
        # create the pyc files, as the build image will be R/O
        process = Popen(
            [six.ensure_text(str(self._creator.exe)), "-m", "compileall", six.ensure_text(str(self._image_dir))],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        process.communicate()
        root_py_cache = self._image_dir / "__pycache__"
        if root_py_cache.exists():
            shutil.rmtree(six.ensure_text(str(root_py_cache)))
        return super(SymlinkPipInstall, self)._generate_new_files()

    def _fix_records(self, new_files):
        new_files_sym = {i for i in new_files if ".." in i.parts}
        new_files_sym.update(i for i in self._image_dir.iterdir())
        extra_record_data_str = self._records_text(sorted(new_files_sym, key=str))
        with open(six.ensure_text(str(self._dist_info / "RECORD")), "wb") as file_handler:
            file_handler.write(extra_record_data_str.encode("utf-8"))

    def build_image(self):
        super(SymlinkPipInstall, self).build_image()
        # protect the image by making it read only
        self._set_tree(self._image_dir, S_IREAD | S_IRGRP | S_IROTH)

    def clear(self):
        if self._image_dir.exists():
            self._set_tree(self._image_dir, S_IWUSR)
        super(SymlinkPipInstall, self).clear()

    @staticmethod
    def _set_tree(folder, stat):
        for root, _, files in os.walk(six.ensure_text(str(folder))):
            for filename in files:
                os.chmod(os.path.join(root, filename), stat)
