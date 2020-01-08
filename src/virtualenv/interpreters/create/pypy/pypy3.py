from __future__ import absolute_import, unicode_literals

import abc

import six

from virtualenv.interpreters.create.support import PosixSupports, Python3Supports, WindowsSupports
from virtualenv.util.path import Path

from .common import PyPy


@six.add_metaclass(abc.ABCMeta)
class PyPy3(PyPy, Python3Supports):
    """"""

    @property
    def exe_base(self):
        return "pypy3"

    def exe_names(self):
        base = super(PyPy3, self).exe_names()
        base.add("pypy")
        return base

    def ensure_directories(self):
        dirs = super(PyPy, self).ensure_directories()
        dirs.add(self.lib_dir / "site-packages")
        return dirs


class PyPy3Posix(PyPy3, PosixSupports):
    """PyPy 2 on POSIX"""

    @property
    def bin_name(self):
        return "bin"

    @property
    def lib_name(self):
        return "lib"

    @property
    def lib_base(self):
        return Path(self.lib_name) / self.interpreter.python_name

    @property
    def _shared_libs(self):
        return ["libpypy3-c.so", "libpypy3-c.dylib"]

    def _shared_lib_to(self):
        return super(PyPy3, self)._shared_lib_to() + [self.dest_dir / self.lib_name]


class Pypy3Windows(PyPy3, WindowsSupports):
    """PyPy 2 on Windows"""

    @property
    def bin_name(self):
        return "Scripts"

    @property
    def lib_name(self):
        return "Lib"

    @property
    def lib_base(self):
        return Path(self.lib_name)

    @property
    def _shared_libs(self):
        return ["libpypy3-c.dll"]
