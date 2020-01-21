from __future__ import absolute_import, unicode_literals

import abc

import six

from virtualenv.create.via_global_ref.builtin.ref import RefToDest
from virtualenv.util.path import Path

from ..python2.python2 import Python2
from .common import CPython, CPythonPosix, CPythonWindows


@six.add_metaclass(abc.ABCMeta)
class CPython2(CPython, Python2):
    """Create a CPython version 2  virtual environment"""

    @classmethod
    def modules(cls):
        return [
            "os",  # landmark to set sys.prefix
        ]


class CPython2Posix(CPython2, CPythonPosix):
    """CPython 2 on POSIX"""

    @classmethod
    def sources(cls, interpreter):
        for src in super(CPythonPosix, cls).sources(interpreter):
            yield src
        # landmark for exec_prefix
        name = "lib-dynload"
        yield RefToDest(Path(interpreter.system_stdlib) / name, dest=cls.to_stdlib)


class CPython2Windows(CPython2, CPythonWindows):
    """CPython 2 on Windows"""

    @classmethod
    def sources(cls, interpreter):
        for src in super(CPython2Windows, cls).sources(interpreter):
            yield src
        py27_dll = Path(interpreter.system_executable).parent / "python27.dll"
        if py27_dll.exists():  # this might be global in the Windows folder in which case it's alright to be missing
            yield RefToDest(py27_dll, dest=cls.to_bin)
