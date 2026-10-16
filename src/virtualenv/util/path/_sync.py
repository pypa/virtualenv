from __future__ import annotations

import logging
import os
import shutil
import sys
from pathlib import Path
from stat import S_IXGRP, S_IXOTH, S_IXUSR
from typing import TYPE_CHECKING, Final

if os.name == "nt":
    from ._win import clear_readonly

if TYPE_CHECKING:
    from collections.abc import Callable
    from types import TracebackType

    _ExcInfo = BaseException | tuple[type[BaseException], BaseException, TracebackType]

LOGGER = logging.getLogger(__name__)


def ensure_dir(path: Path) -> None:
    if not path.exists():
        LOGGER.debug("create folder %s", path)
        os.makedirs(str(path))


def write_file(path: Path, data: bytes) -> None:
    if path.is_symlink() or path.exists():
        path.unlink()
    # Exclusive creation rejects links introduced after the old entry was removed.
    with path.open("xb") as stream:
        stream.write(data)


def ensure_safe_to_do(src: Path, dest: Path) -> None:
    if src == dest:
        msg = f"source and destination is the same {src}"
        raise ValueError(msg)
    if not dest.exists() and not dest.is_symlink():
        return
    if dest.is_dir() and not dest.is_symlink():
        LOGGER.debug("remove directory %s", dest)
        safe_delete(dest)
    else:
        LOGGER.debug("remove file %s", dest)
        dest.unlink()


def symlink(src: Path, dest: Path) -> None:
    ensure_safe_to_do(src, dest)
    LOGGER.debug("symlink %s", _Debug(src, dest))
    dest.symlink_to(src, target_is_directory=src.is_dir())


def copy(src: Path, dest: Path) -> None:
    LOGGER.debug("copy %s", _Debug(src, dest))
    if src.is_dir():
        ensure_safe_to_do(src, dest)
        copytree(str(src), str(dest))
    else:
        _copy_file(src, dest)


def copytree(src: str, dest: str) -> None:
    for root, _, files in os.walk(src):
        dest_dir: Final = Path(dest) / os.path.relpath(root, src)
        dest_dir.mkdir(parents=True, exist_ok=True)
        for name in files:
            _copy_file(Path(root) / name, dest_dir / name)


def _copy_file(src: Path, dest: Path) -> None:
    ensure_safe_to_do(src, dest)
    mode: Final = 0o755 if src.stat().st_mode & (S_IXUSR | S_IXGRP | S_IXOTH) else 0o644
    flags: Final = os.O_WRONLY | os.O_CREAT | os.O_EXCL | (os.O_BINARY if os.name == "nt" else 0)
    # Creation applies the current umask without changing the process-wide setting.
    with src.open("rb") as source, os.fdopen(os.open(str(dest), flags, mode), "wb") as target:
        shutil.copyfileobj(source, target, length=1024 * 1024)


def safe_delete(dest: Path) -> None:
    def onerror(func: Callable[[str], object], path: str, exc_info: _ExcInfo) -> None:
        exc = exc_info[1] if isinstance(exc_info, tuple) else exc_info
        if isinstance(exc, FileNotFoundError):
            return
        # POSIX deletion depends on the parent directory, so changing the entry's mode cannot help.
        if os.name != "nt" or func not in {os.unlink, os.rmdir} or os.path.islink(path) or os.access(path, os.W_OK):
            raise exc
        clear_readonly(path)
        func(path)

    if sys.version_info >= (3, 12):
        shutil.rmtree(str(dest), onexc=onerror)
    else:
        shutil.rmtree(str(dest), onerror=onerror)


class _Debug:
    def __init__(self, src: Path, dest: Path) -> None:
        self.src = src
        self.dest = dest

    def __str__(self) -> str:
        return f"{'directory ' if self.src.is_dir() else ''}{self.src!s} to {self.dest!s}"


__all__ = [
    "copy",
    "copytree",
    "ensure_dir",
    "safe_delete",
    "symlink",
    "write_file",
]
