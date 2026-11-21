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

    def _install_files(self, dist_info: Path, /) -> list[str]:
        files: list[str] = []
        modules: set[str] = set()
        purelib = str(self._creator.purelib)
        record = os.path.normcase(dist_info / "RECORD")
        with os.scandir(self._image_dir) as entries:
            for entry in entries:
                self._install_entry(entry, purelib, record if entry.name == dist_info.name else None, files)
                if entry.name.endswith(".py") and entry.is_file(follow_symlinks=False):
                    modules.add(entry.name[:-3])
        # Root bytecode is compiled in the target interpreter and omitted from the shared image.
        with (dist_info / "RECORD").open(encoding="utf-8", newline="") as stream:
            for row in csv.reader(stream):
                if not row or not row[0].startswith(f"__pycache__{os.sep}"):
                    continue
                cached = self._creator.purelib / row[0]
                if cached.parent == self._creator.purelib / "__pycache__" and cached.suffix == ".pyc":
                    module, _, tag = cached.stem.rpartition(".")
                    if module in modules and tag:
                        files.append(row[0])
        return files

    def _install_entry(self, src: os.DirEntry[str], parent: str, record: str | None, files: list[str]) -> None:
        dst = os.path.join(parent, src.name)
        info = src.stat(follow_symlinks=False)
        if self._redirects(info):
            msg = f"refusing to link a redirected seed image entry: {src.path}"
            raise RuntimeError(msg)
        if stat.S_ISDIR(info.st_mode):
            # pip unlinks files before replacement but writes through a linked directory.
            created = self._mkdir(dst, (info.st_mode & 0o077) | 0o700)
            previous_count = len(files)
            with os.scandir(src.path) as entries:
                for child in entries:
                    self._install_entry(child, dst, record, files)
            if created and len(files) == previous_count:
                # Empty directories have no RECORD entry to remove on a subsequent install.
                os.rmdir(dst)
            return
        if not stat.S_ISREG(info.st_mode):
            msg = f"refusing to link a non-regular seed image entry: {src.path}"
            raise RuntimeError(msg)
        files.append(src.path.removeprefix(f"{self._image_dir}{os.sep}"))
        if record is None:
            self._link_file(src.path, dst)
        elif os.path.normcase(src.path) != record:
            flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
            mode = (info.st_mode & (S_IREAD | S_IRGRP | S_IROTH)) | S_IWUSR
            with os.fdopen(os.open(dst, flags, mode), "wb") as output, open(src.path, "rb") as source:
                shutil.copyfileobj(source, output)

    @staticmethod
    def _redirects(info: os.stat_result) -> bool:
        return stat.S_ISLNK(info.st_mode) or (os.name == "nt" and bool(info.st_reparse_tag & 0x2000_0000))

    @staticmethod
    def _mkdir(dst: str, mode: int) -> bool:
        try:
            os.mkdir(dst, mode)
        except FileExistsError:
            # A previous install can stop before it writes RECORD. Reuse only real directories.
            info = os.lstat(dst)
            if not stat.S_ISDIR(info.st_mode) or SymlinkPipInstall._redirects(info):
                raise
            return False
        return True

    @staticmethod
    def _link_file(src: str, dst: str) -> None:
        try:
            os.symlink(src, dst)
        except FileExistsError:
            if not os.path.islink(dst) or not os.path.samefile(src, dst):
                raise

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
