from __future__ import absolute_import, unicode_literals

import abc

import six

from virtualenv.create.describe import PosixSupports, WindowsSupports

from ..python2.python2 import Python2
from .common import PyPy


@six.add_metaclass(abc.ABCMeta)
class PyPy2(PyPy, Python2):
    """"""

    @classmethod
    def exe_stem(cls):
        return "pypy"

    @property
    def lib_pypy(self):
        return self.dest / "lib_pypy"

    def ensure_directories(self):
        return super(PyPy, self).ensure_directories() | {self.lib_pypy}

    @classmethod
    def modules(cls):
        # pypy2 uses some modules before the site.py loads, so we need to include these too
        return super(PyPy2, cls).modules() + [
            "copy_reg",
            "genericpath",
            "linecache",
            "os",
            "stat",
            "UserDict",
            "warnings",
        ]


class PyPy2Posix(PyPy2, PosixSupports):
    """PyPy 2 on POSIX"""

    @classmethod
    def modules(cls):
        return super(PyPy2Posix, cls).modules() + ["posixpath"]

    @classmethod
    def _shared_libs(cls):
        return ["libpypy-c.so", "libpypy-c.dylib"]


class Pypy2Windows(PyPy2, WindowsSupports):
    """PyPy 2 on Windows"""

    @classmethod
    def modules(cls):
        return super(Pypy2Windows, cls).modules() + ["ntpath"]

    @classmethod
    def _shared_libs(cls):
        return ["libpypy-c.dll"]
