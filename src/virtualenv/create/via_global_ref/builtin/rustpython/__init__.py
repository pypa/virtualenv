from __future__ import annotations

from abc import ABC
from pathlib import Path

from virtualenv.create.describe import PosixSupports, Python3Supports, WindowsSupports
from virtualenv.create.via_global_ref.builtin.ref import RefMust, RefWhen
from virtualenv.create.via_global_ref.builtin.via_global_self_do import ViaGlobalRefVirtualenvBuiltin


class RustPython(ViaGlobalRefVirtualenvBuiltin, Python3Supports, ABC):
    @classmethod
    def can_describe(cls, interpreter):
        return interpreter.implementation == "RustPython" and super().can_describe(interpreter)

    @classmethod
    def exe_stem(cls):
        return "rustpython"

    @classmethod
    def exe_names(cls, interpreter):
        return {
            cls.exe_stem(),
            "python",
            f"python{interpreter.version_info.major}",
            f"python{interpreter.version_info.major}.{interpreter.version_info.minor}",
        }

    @classmethod
    def _executables(cls, interpreter):
        host = Path(interpreter.system_executable)
        targets = sorted(f"{name}{cls.suffix}" for name in cls.exe_names(interpreter))
        yield host, targets, RefMust.NA, RefWhen.ANY


class RustPythonPosix(RustPython, PosixSupports):
    """RustPython on POSIX."""


class RustPythonWindows(RustPython, WindowsSupports):
    """RustPython on Windows."""


__all__ = [
    "RustPythonPosix",
    "RustPythonWindows",
]
