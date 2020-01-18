from __future__ import absolute_import, unicode_literals

import abc

import six

from virtualenv.interpreters.create.support import PosixSupports, WindowsSupports
from virtualenv.interpreters.create.via_global_ref.python2 import Python2

from .common import PyPy


@six.add_metaclass(abc.ABCMeta)
class PyPy2(PyPy, Python2):
    """"""

    @property
    def exe_base(self):
        return "pypy"

    @property
    def lib_pypy(self):
        return self.dest_dir / "lib_pypy"

    def _calc_config_vars(self, to):
        base = super(PyPy, self)._calc_config_vars(to)
        # for some reason pypy seems to provide the wrong information for implementation_lower, fix it
        base["implementation_lower"] = "python"
        return base

    def ensure_directories(self):
        return super(PyPy, self).ensure_directories() | {self.lib_pypy}

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

    def modules(self):
        return super(PyPy2Posix, self).modules() + ["posixpath"]

    @property
    def _shared_libs(self):
        return ["libpypy-c.so", "libpypy-c.dylib"]


class Pypy2Windows(PyPy2, WindowsSupports):
    """PyPy 2 on Windows"""

    def modules(self):
        return super(Pypy2Windows, self).modules() + ["ntpath"]

    @property
    def _shared_libs(self):
        return ["libpypy-c.dll"]
