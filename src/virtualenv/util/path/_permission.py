from __future__ import annotations

import errno
import os
import sys
from stat import S_IXGRP, S_IXOTH, S_IXUSR
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


def owner_executable_mode(directory: Path, mode: int) -> int:
    """Allow owner execute when the umask alone withheld it.

    :param directory: the directory where the executable was created
    :param mode: the file's permission bits at creation

    :returns: the permission bits for an owner-executable copy

    :raises PermissionError: when the directory's access policy may forbid owner execute
    :raises OSError: when reading the directory's default ACL fails

    """
    if mode & S_IXUSR:
        return mode
    if sys.platform == "linux" and hasattr(os, "getxattr"):
        try:
            os.getxattr(directory, "system.posix_acl_default")
        except OSError as exc:
            if exc.errno in {errno.ENODATA, errno.ENOTSUP}:
                return mode | S_IXUSR
            raise
    msg = f"cannot create an owner-executable copy in {directory}; check the default ACL or use --symlinks"
    raise PermissionError(msg)


def make_exe(filename: Path) -> None:
    """Make a file executable for the classes that can read it, dropping classes the change is refused for.

    :param filename: the file to make executable

    """
    original_mode = filename.stat().st_mode
    levels = [S_IXUSR, S_IXGRP, S_IXOTH]
    for at in range(len(levels), 0, -1):
        try:
            mode = original_mode
            for level in levels[:at]:
                mode |= level
            filename.chmod(mode)
            break
        except OSError:
            continue


def set_tree(folder: Path, stat: int) -> None:
    """Limit the mode of every file below a folder.

    :param folder: the folder to walk
    :param stat: the permission bits to keep on each file

    """
    for root, _, files in os.walk(str(folder)):
        for filename in files:
            path = os.path.join(root, filename)
            os.chmod(path, os.stat(path).st_mode & stat)


__all__ = [
    "make_exe",
    "owner_executable_mode",
    "set_tree",
]
