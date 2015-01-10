from __future__ import absolute_import, division, print_function

import os
import re
import shutil
import stat


def ensure_directory(directory, *args, **kwargs):
    # Fail if the destination exists and it's not a directory
    if not os.path.isdir(directory):
        os.makedirs(directory, *args, **kwargs)


def copyfile(srcfile, destfile, skip=re.compile(r".*\.pyc\Z|__pycache__\Z", re.IGNORECASE)):
    ensure_directory(os.path.dirname(destfile))

    if os.path.isdir(srcfile):
        # TODO: just use shutil.copytree to avoid bikeshedding
        for name in os.listdir(srcfile):
            if not skip.match(name):
                copyfile(
                    os.path.join(srcfile, name),
                    os.path.join(destfile, name)
                )
    else:
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


class cached_property(object):  # flake8: noqa
    def __init__(self, func):
        self.__doc__ = getattr(func, '__doc__')
        self.func = func

    def __get__(self, obj, cls):
        if obj is None:
            return self
        value = obj.__dict__[self.func.__name__] = self.func(obj)
        return value
