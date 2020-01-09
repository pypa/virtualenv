from __future__ import absolute_import, unicode_literals

import abc

import six

from virtualenv.interpreters.create.support import PosixSupports, WindowsSupports
from virtualenv.interpreters.create.via_global_ref.python2 import Python2
from virtualenv.util.path import Path

from .common import PyPy


@six.add_metaclass(abc.ABCMeta)
class PyPy2(PyPy, Python2):
    """"""

    @property
    def exe_base(self):
        return "pypy"

    @property
    def lib_name(self):
        return "lib-python"

    @property
    def lib_pypy(self):
        return self.dest_dir / "lib_pypy"

    @property
    def lib_base(self):
        return Path(self.lib_name) / self.interpreter.version_release_str

    def ensure_directories(self):
        dirs = super(PyPy, self).ensure_directories()
        dirs.add(self.lib_pypy)
        return dirs

    def modules(self):
        return [
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

    @property
    def bin_name(self):
        return "bin"

    def modules(self):
        return super(PyPy2Posix, self).modules() + ["posixpath"]

    @property
    def _shared_libs(self):
        return ["libpypy-c.so", "libpypy-c.dylib"]


class Pypy2Windows(PyPy2, WindowsSupports):
    """PyPy 2 on Windows"""

    @property
    def bin_name(self):
        return "Scripts"

    def modules(self):
        return super(Pypy2Windows, self).modules() + ["ntpath"]

    @property
    def _shared_libs(self):
        return ["libpypy-c.dll"]
