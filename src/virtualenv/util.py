from __future__ import absolute_import, unicode_literals

import logging
import os
import shutil
import subprocess
from functools import partial
from os import makedirs

import six


def ensure_dir(path):
    if not path.exists():
        logging.debug("created %s", path)
        makedirs(six.text_type(path))


HAS_SYMLINK = hasattr(os, "symlink")


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
                    os.symlink(src.name, six.text_type(dst))
                else:
                    os.symlink(six.text_type(src), six.text_type(dst))
        except OSError as exception:
            logging.warning("symlink failed %r, for %s to %s, will try copy", exception, src, dst)
            do_copy = True
    if do_copy:
        copier = shutil.copy2 if src.is_file() else shutil.copytree
        copier(six.text_type(src), six.text_type(dst))
    logging.debug("%s %s to %s", "copy" if do_copy else "symlink", src, dst)


def run_cmd(cmd):
    try:
        process = subprocess.Popen(
            cmd, universal_newlines=True, stdin=subprocess.PIPE, stderr=subprocess.PIPE, stdout=subprocess.PIPE
        )
        out, err = process.communicate()  # input disabled
        code = process.returncode
    except OSError as os_error:
        code, out, err = os_error.errno, "", os_error.strerror
    return code, out, err


symlink = partial(symlink_or_copy, False)
copy = partial(symlink_or_copy, True)
