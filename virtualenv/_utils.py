from __future__ import absolute_import, division, print_function

import errno
import os
import shutil
import stat


def ensure_directory(directory, *args, **kwargs):
    try:
        os.makedirs(directory, *args, **kwargs)
    except OSError as exc:
        if exc.errno != errno.EEXIST:
            raise


def copyfile(srcfile, destfile):
    # We use copyfile (not move, copy, or copy2) to be extra sure that we are
    # not moving directories over (copyfile fails for directories) as well as
    # to ensure that we are not copying over any metadata because we want more
    # control over what metadata we actually copy over.
    shutil.copyfile(srcfile, destfile)

    # Grab the stat data for the source file so we can use it to copy over
    # certain metadata to the destination file.
    st = os.stat(srcfile)

    # If our file is executable, then make our destination file
    # executable.
    if os.access(srcfile, os.X_OK):
        permissions = st.st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH
        os.chmod(destfile, permissions)
