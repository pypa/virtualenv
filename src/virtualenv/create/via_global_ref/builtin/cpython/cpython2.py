from __future__ import absolute_import, unicode_literals

import abc
import logging

import six

from virtualenv.create.via_global_ref.builtin.ref import PathRefToDest
from virtualenv.util.path import Path

from ..python2.python2 import Python2
from .common import CPython, CPythonPosix, CPythonWindows


@six.add_metaclass(abc.ABCMeta)
class CPython2(CPython, Python2):
    """Create a CPython version 2  virtual environment"""

    @classmethod
    def sources(cls, interpreter):
        for src in super(CPython2, cls).sources(interpreter):
            yield src
        # include folder needed on Python 2 as we don't have pyenv.cfg
        host_include_marker = cls.host_include_marker(interpreter)
        if host_include_marker.exists():
            yield PathRefToDest(host_include_marker.parent, dest=lambda self, _: self.include)

    @classmethod
    def host_include_marker(cls, interpreter):
        return Path(interpreter.system_include) / "Python.h"

    @property
    def include(self):
        # the pattern include the distribution name too at the end, remove that via the parent call
        return (self.dest / self.interpreter.distutils_install["headers"]).parent

    @classmethod
    def modules(cls):
        return [
            "os",  # landmark to set sys.prefix
        ]

    def ensure_directories(self):
        dirs = super(CPython2, self).ensure_directories()
        host_include_marker = self.host_include_marker(self.interpreter)
        if host_include_marker.exists():
            dirs.add(self.include.parent)
        else:
            logging.debug("no include folders as can't find include marker %s", host_include_marker)
        return dirs


class CPython2Posix(CPython2, CPythonPosix):
    """CPython 2 on POSIX"""

    @classmethod
    def sources(cls, interpreter):
        for src in super(CPython2Posix, cls).sources(interpreter):
            yield src
        # landmark for exec_prefix
        name = "lib-dynload"
        yield PathRefToDest(Path(interpreter.system_stdlib) / name, dest=cls.to_stdlib)


class CPython2Windows(CPython2, CPythonWindows):
    """CPython 2 on Windows"""

    @classmethod
    def sources(cls, interpreter):
        for src in super(CPython2Windows, cls).sources(interpreter):
            yield src
        py27_dll = Path(interpreter.system_executable).parent / "python27.dll"
        if py27_dll.exists():  # this might be global in the Windows folder in which case it's alright to be missing
            yield PathRefToDest(py27_dll, dest=cls.to_bin)

        libs = Path(interpreter.system_prefix) / "libs"
        if libs.exists():
            yield PathRefToDest(libs, dest=lambda self, s: self.dest / s.name)
