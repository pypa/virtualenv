from __future__ import absolute_import, unicode_literals

import os
import sys

import attr


@attr.s
class BaseOption(object):
    """
    Virtual Environment base options

    :ivar verbose: logging verbosity level, default to INFO
    :ivar python: the python specifier, defaults to current interpret
    """

    quiet = attr.ib(default=0, type=int)
    verbose = attr.ib(default=3, type=int)
    python = attr.ib(default=sys.executable, type=str)

    @property
    def verbosity(self):
        return max(self.verbose - self.quiet, 0)


@attr.s
class RunOption(BaseOption):
    """
    Virtual Environment creation options
    """

    clear = attr.ib(default=False, type=bool)
    dest_dir = attr.ib(default=None, type=str)
    prompt = attr.ib(default=None, type=str)

    # seed package
    without_pip = attr.ib(default=False, type=bool)
    download = attr.ib(default=False, type=bool)
    pip = attr.ib(default=None, type=str)
    setuptools = attr.ib(default=None, type=str)

    no_venv = attr.ib(default=False, type=bool)
    system_site = attr.ib(default=False, type=bool)
    symlinks = attr.ib(default=os.name != "nt", type=bool)
