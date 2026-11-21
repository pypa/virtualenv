from __future__ import annotations

__lazy_modules__ = [
    "csv",
    "shutil",
    "virtualenv.util.error",
    "virtualenv.util.path",
    "virtualenv.util.subprocess",
]

import csv
import os
import shutil
import stat
from stat import S_IREAD, S_IRGRP, S_IROTH, S_IWUSR
from typing import TYPE_CHECKING

from virtualenv.util.error import ProcessCallFailedError
from virtualenv.util.path import safe_delete, set_tree
from virtualenv.util.subprocess import run_cmd

from .base import PipInstall

if TYPE_CHECKING:
    import zipfile
    from pathlib import Path


class SymlinkPipInstall(PipInstall):
    """Install a seed package by symlinking its image files into the environment."""

    def _install_files(self, dist_info: Path, /) -> list[Path]:
        files: list[Path] = []
        for child in self._image_dir.iterdir():
            self._install_entry(child, self._creator.purelib / child.name, dist_info, files)
        # Root bytecode is compiled in the target interpreter and omitted from the shared image.
        modules = {path.stem for path in files if path.parent == self._creator.purelib and path.suffix == ".py"}
        with (dist_info / "RECORD").open(encoding="utf-8", newline="") as stream:
            for row in csv.reader(stream):
                if not row or not row[0].startswith(f"__pycache__{os.sep}"):
                    continue
                cached = self._creator.purelib / row[0]
                if cached.parent == self._creator.purelib / "__pycache__" and cached.suffix == ".pyc":
                    module, _, tag = cached.stem.rpartition(".")
                    if module in modules and tag:
                        files.append(cached)
        return files

    def _install_entry(self, src: Path, dst: Path, dist_info: Path, files: list[Path]) -> None:
        info = src.lstat()
        if stat.S_ISLNK(info.st_mode) or (os.name == "nt" and info.st_reparse_tag & 0x2000_0000):
            msg = f"refusing to link a redirected seed image entry: {src}"
            raise RuntimeError(msg)
        if stat.S_ISDIR(info.st_mode):
            # pip unlinks files before replacement but writes through a linked directory.
            dst.mkdir(mode=(info.st_mode & 0o077) | 0o700)
            for child in src.iterdir():
                self._install_entry(child, dst / child.name, dist_info, files)
            return
        if not stat.S_ISREG(info.st_mode):
            msg = f"refusing to link a non-regular seed image entry: {src}"
            raise RuntimeError(msg)
        files.append(dst)
        if dist_info not in src.parents:
            dst.symlink_to(src)
        elif src != dist_info / "RECORD":
            flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
            mode = (info.st_mode & (S_IREAD | S_IRGRP | S_IROTH)) | S_IWUSR
            with os.fdopen(os.open(dst, flags, mode), "wb") as output, src.open("rb") as source:
                shutil.copyfileobj(source, output)

    def _generate_new_files(self, folder: Path, dist_info: Path) -> set[Path]:
        # create the pyc files, as the build image will be R/O
        cmd = [
            str(self._creator.exe),
            "-S",
            "-c",
            (
                "import sys; sys.path[:] = [p for p in sys.path if p != '']; "
                "import runpy; runpy.run_module('compileall', run_name='__main__', alter_sys=True)"
            ),
            str(folder),
        ]
        code, out, err = run_cmd(cmd, env={**self._creator.env, "PYTHONSAFEPATH": "1"})
        if code != 0:
            raise ProcessCallFailedError(code, out, err, cmd)
        # the root pyc is shared, so we'll not symlink that - but still add the pyc files to the RECORD for close
        root_py_cache = folder / "__pycache__"
        new_files = set()
        if root_py_cache.exists():
            new_files.update(root_py_cache.iterdir())
            new_files.add(root_py_cache)
            safe_delete(root_py_cache)
        core_new_files = super()._generate_new_files(folder, dist_info)
        # remove files that are within the image folder deeper than one level (as these will be not linked directly)
        for file in core_new_files:
            try:
                if len(file.relative_to(folder).parts) > 1:
                    continue
            except ValueError:
                pass
            new_files.add(file)
        return new_files

    def _fix_records(self, folder: Path, dist_info: Path, extra_record_data: set[Path]) -> None:
        extra_record_data.update(folder.iterdir())
        extra_record_data_str = self._records_text(folder, sorted(extra_record_data, key=str))
        with (dist_info / "RECORD").open("w", encoding="utf-8", newline="") as stream:
            stream.write(extra_record_data_str)

    def _populate_image(self, zip_ref: zipfile.ZipFile, folder: Path) -> None:
        super()._populate_image(zip_ref, folder)
        # protect the image by making it read only
        set_tree(folder, S_IREAD | S_IRGRP | S_IROTH)

    def clear(self) -> None:
        """Remove the cached image of the wheel, linked files included."""
        if self._image_dir.exists():
            safe_delete(self._image_dir)
        super().clear()


__all__ = [
    "SymlinkPipInstall",
]
