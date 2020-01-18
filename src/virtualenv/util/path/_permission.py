from __future__ import absolute_import, unicode_literals

from stat import S_IXGRP, S_IXOTH, S_IXUSR


def make_exe(filename):
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


__all__ = ("make_exe",)
