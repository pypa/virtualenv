from __future__ import absolute_import, unicode_literals

import logging
import os
import shutil
from functools import partial

import six

HAS_SYMLINK = hasattr(os, "symlink")


def ensure_dir(path):
    if not path.exists():
        logging.debug("created %s", six.ensure_text(str(path)))
        os.makedirs(six.ensure_text(str(path)))


def symlink_or_copy(do_copy, src, dst, relative_symlinks_ok=False):
    """
    Try symlinking a target, and if that fails, fall back to copying.
    """
    if do_copy is False and HAS_SYMLINK is False:  # if no symlink, always use copy
        do_copy = True
    if not do_copy:
        try:
            if not dst.is_symlink():  # can't link to itself!
                if relative_symlinks_ok:
                    assert src.parent == dst.parent
                    os.symlink(six.ensure_text(src.name), six.ensure_text(str(dst)))
                else:
                    os.symlink(six.ensure_text(str(src)), six.ensure_text(str(dst)))
        except OSError as exception:
            logging.warning(
                "symlink failed %r, for %s to %s, will try copy",
                exception,
                six.ensure_text(str(src)),
                six.ensure_text(str(dst)),
            )
            do_copy = True
    if do_copy:
        copier = shutil.copy2 if src.is_file() else shutil.copytree
        copier(six.ensure_text(str(src)), six.ensure_text(str(dst)))
    logging.debug("%s %s to %s", "copy" if do_copy else "symlink", six.ensure_text(str(src)), six.ensure_text(str(dst)))


symlink = partial(symlink_or_copy, False)
copy = partial(symlink_or_copy, True)

__all__ = ("ensure_dir", "symlink", "copy", "symlink_or_copy")
