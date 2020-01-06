from __future__ import absolute_import, unicode_literals

import abc

import six

from virtualenv.interpreters.create.support import PosixSupports, WindowsSupports
from virtualenv.interpreters.create.via_global_ref.via_global_self_do import ViaGlobalRefSelfDo
from virtualenv.util.path import Path


@six.add_metaclass(abc.ABCMeta)
class CPython(ViaGlobalRefSelfDo):
    @classmethod
    def supports(cls, interpreter):
        return interpreter.implementation == "CPython" and super(CPython, cls).supports(interpreter)

    @property
    def exe_name(self):
        return "python"


@six.add_metaclass(abc.ABCMeta)
class CPythonPosix(CPython, PosixSupports):
    """Create a CPython virtual environment on POSIX platforms"""

    @property
    def bin_name(self):
        return "bin"

    @property
    def lib_name(self):
        return "lib"

    @property
    def lib_base(self):
        return Path(self.lib_name) / self.interpreter.python_name

    def link_exe(self):
        host = Path(self.interpreter.system_executable)
        major, minor = self.interpreter.version_info.major, self.interpreter.version_info.minor
        return {host: sorted({host.name, "python", "python{}".format(major), "python{}.{}".format(major, minor)})}


@six.add_metaclass(abc.ABCMeta)
class CPythonWindows(CPython, WindowsSupports):
    @property
    def bin_name(self):
        return "Scripts"

    @property
    def lib_name(self):
        return "Lib"

    @property
    def lib_base(self):
        return Path(self.lib_name)

    def link_exe(self):
        host = Path(self.interpreter.system_executable)
        return {p: [p.name] for p in (host.parent / n for n in ("python.exe", "pythonw.exe", host.name)) if p.exists()}
