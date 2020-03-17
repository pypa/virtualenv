from __future__ import absolute_import, unicode_literals

import abc

from six import add_metaclass

from virtualenv.create.describe import Python3Supports
from virtualenv.create.via_global_ref.builtin.ref import PathRefToDest
from virtualenv.create.via_global_ref.store import is_store_python
from virtualenv.util.path import Path

from .common import CPython, CPythonPosix, CPythonWindows, is_mac_os_framework


@add_metaclass(abc.ABCMeta)
class CPython3(CPython, Python3Supports):
    """"""


class CPython3Posix(CPythonPosix, CPython3):
    @classmethod
    def can_describe(cls, interpreter):
        return is_mac_os_framework(interpreter) is False and super(CPython3Posix, cls).can_describe(interpreter)


class CPython3Windows(CPythonWindows, CPython3):
    """"""

    @classmethod
    def setup_meta(cls, interpreter):
        if is_store_python(interpreter):  # store python is not supported here
            return None
        return super(CPython3Windows, cls).setup_meta(interpreter)

    @classmethod
    def sources(cls, interpreter):
        for src in super(CPython3Windows, cls).sources(interpreter):
            yield src
        for src in cls.include_dll_and_pyd(interpreter):
            yield src

    @classmethod
    def include_dll_and_pyd(cls, interpreter):
        dll_folder = Path(interpreter.system_prefix) / "DLLs"
        host_exe_folder = Path(interpreter.system_executable).parent
        for folder in [host_exe_folder, dll_folder]:
            for file in folder.iterdir():
                if file.suffix in (".pyd", ".dll"):
                    yield PathRefToDest(file, dest=cls.to_dll_and_pyd)

    def to_dll_and_pyd(self, src):
        return self.bin_dir / src.name
