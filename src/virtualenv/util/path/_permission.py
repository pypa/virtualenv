from __future__ import annotations

import os
from stat import S_IXGRP, S_IXOTH, S_IXUSR
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


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
    """Set the mode of every file below a folder.

    :param folder: the folder to walk
    :param stat: the mode to set on each file

    """
    for root, _, files in os.walk(str(folder)):
        for filename in files:
            os.chmod(os.path.join(root, filename), stat)


__all__ = [
    "make_exe",
    "set_tree",
]
