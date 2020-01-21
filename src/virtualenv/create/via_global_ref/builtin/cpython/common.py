from __future__ import absolute_import, unicode_literals

from abc import ABCMeta
from collections import OrderedDict

from six import add_metaclass

from virtualenv.create.describe import PosixSupports, WindowsSupports
from virtualenv.util.path import Path

from ..via_global_self_do import ViaGlobalRefVirtualenvBuiltin


@add_metaclass(ABCMeta)
class CPython(ViaGlobalRefVirtualenvBuiltin):
    @classmethod
    def can_describe(cls, interpreter):
        return interpreter.implementation == "CPython" and super(CPython, cls).can_describe(interpreter)

    @classmethod
    def exe_stem(cls):
        return "python"


@add_metaclass(ABCMeta)
class CPythonPosix(CPython, PosixSupports):
    """Create a CPython virtual environment on POSIX platforms"""

    @classmethod
    def _executables(cls, interpreter):
        host_exe = Path(interpreter.system_executable)
        major, minor = interpreter.version_info.major, interpreter.version_info.minor
        targets = OrderedDict(
            (i, None) for i in ["python", "python{}".format(major), "python{}.{}".format(major, minor), host_exe.name]
        )
        yield host_exe, list(targets.keys())


@add_metaclass(ABCMeta)
class CPythonWindows(CPython, WindowsSupports):
    @classmethod
    def _executables(cls, interpreter):
        host = Path(interpreter.system_executable)
        for path in (host.parent / n for n in ("python.exe", "pythonw.exe", host.name)):
            yield host, [path.name]
