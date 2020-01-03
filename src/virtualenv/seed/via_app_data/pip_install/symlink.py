from __future__ import absolute_import, unicode_literals

import os
import shutil
import subprocess

import six

from virtualenv.util.subprocess import Popen

from .base import PipInstall


class SymlinkPipInstall(PipInstall):
    def sync(self, src, dst):
        src_str = six.ensure_text(str(src))
        dest_str = six.ensure_text(str(dst))
        os.symlink(src_str, dest_str)

    def _generate_new_files(self):
        # create the pyc files, as the build image will be R/O
        process = Popen(
            [six.ensure_text(str(self.creator.exe)), "-m", "compileall", six.ensure_text(str(self.image_folder))],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        process.communicate()
        root_py_cache = self.image_folder / "__pycache__"
        if root_py_cache.exists():
            shutil.rmtree(six.ensure_text(str(root_py_cache)))
        return super(SymlinkPipInstall, self)._generate_new_files()

    def _fix_records(self, new_files):
        new_files_sym = {i for i in new_files if ".." in i.parts}
        new_files_sym.update(i for i in self.image_folder.iterdir())
        extra_record_data_str = self._records_text(sorted(new_files_sym, key=str))
        with open(six.ensure_text(str(self.dist_info / "RECORD")), "wb") as file_handler:
            file_handler.write(extra_record_data_str.encode("utf-8"))
