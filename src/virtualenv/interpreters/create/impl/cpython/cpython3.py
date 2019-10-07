from __future__ import absolute_import, unicode_literals

import abc

import six
from pathlib2 import Path

from virtualenv.util import copy

from .common import CPython, CPythonPosix, CPythonWindows


@six.add_metaclass(abc.ABCMeta)
class CPython3(CPython):
    """"""


class CPython3Posix(CPythonPosix, CPython3):
    """"""


class CPython3Windows(CPythonWindows, CPython3):
    """"""

    def setup_python(self):
        super(CPython3Windows, self).setup_python()
        self.include_dll()

    def include_dll(self):
        dll_folder = Path(self.interpreter.system_prefix) / "DLLs"
        host_exe_folder = Path(self.interpreter.system_executable).parent
        for folder in [host_exe_folder, dll_folder]:
            for file in folder.iterdir():
                if file.suffix in (".pyd", ".dll"):
                    copy(file, self.bin_dir / file.name)
