from __future__ import absolute_import, unicode_literals

import abc

import six

from virtualenv.interpreters.create.support import PosixSupports, Python3Supports, WindowsSupports

from .common import PyPy


@six.add_metaclass(abc.ABCMeta)
class PyPy3(PyPy, Python3Supports):
    @property
    def exe_base(self):
        return "pypy3"

    @property
    def stdlib(self):
        """
        PyPy3 seems to respect sysconfig only for the host python...
        virtual environments purelib is instead lib/pythonx.y
        """
        return self.dest_dir / "lib" / "python{}".format(self.interpreter.version_release_str) / "site-packages"

    def exe_names(self):
        base = super(PyPy3, self).exe_names()
        base.add("pypy")
        return base


class PyPy3Posix(PyPy3, PosixSupports):
    """PyPy 2 on POSIX"""

    @property
    def _shared_libs(self):
        return ["libpypy3-c.so", "libpypy3-c.dylib"]

    def _shared_lib_to(self):
        return super(PyPy3, self)._shared_lib_to() + [self.stdlib.parent.parent]


class Pypy3Windows(PyPy3, WindowsSupports):
    """PyPy 2 on Windows"""

    @property
    def bin_dir(self):
        """PyPy3 needs to fallback to pypy definition"""
        return self.dest_dir / "Scripts"

    @property
    def _shared_libs(self):
        return ["libpypy3-c.dll"]
