from __future__ import absolute_import, unicode_literals

import abc

import six

from virtualenv.interpreters.create.support import PosixSupports, WindowsSupports
from virtualenv.interpreters.create.via_global_ref.via_global_self_do import ViaGlobalRefVirtualenvBuiltin
from virtualenv.util.path import Path


@six.add_metaclass(abc.ABCMeta)
class CPython(ViaGlobalRefVirtualenvBuiltin):
    @classmethod
    def supports(cls, interpreter):
        return interpreter.implementation == "CPython" and super(CPython, cls).supports(interpreter)

    @property
    def exe_base(self):
        return "python"


@six.add_metaclass(abc.ABCMeta)
class CPythonPosix(CPython, PosixSupports):
    """Create a CPython virtual environment on POSIX platforms"""

    def link_exe(self):
        host = Path(self.interpreter.system_executable)
        major, minor = self.interpreter.version_info.major, self.interpreter.version_info.minor
        return {host: sorted({host.name, "python", "python{}".format(major), "python{}.{}".format(major, minor)})}


@six.add_metaclass(abc.ABCMeta)
class CPythonWindows(CPython, WindowsSupports):
    def link_exe(self):
        host = Path(self.interpreter.system_executable)
        return {p: [p.name] for p in (host.parent / n for n in ("python.exe", "pythonw.exe", host.name)) if p.exists()}
