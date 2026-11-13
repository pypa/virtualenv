from __future__ import annotations

from abc import ABC  # simplint: ignore[init-module-content]  # preserve class __module__
from pathlib import Path  # simplint: ignore[init-module-content]  # preserve class __module__
from typing import TYPE_CHECKING  # simplint: ignore[init-module-content]  # preserve class __module__

from virtualenv.create.describe import (  # simplint: ignore[init-module-content]  # preserve class __module__
    PosixSupports,
    Python3Supports,
    WindowsSupports,
)
from virtualenv.create.via_global_ref.builtin.ref import (  # simplint: ignore[init-module-content] preserve API
    RefMust,
    RefWhen,
)
from virtualenv.create.via_global_ref.builtin.via_global_self_do import (  # simplint: ignore[init-module-content] API
    ViaGlobalRefVirtualenvBuiltin,
)

if TYPE_CHECKING:
    from collections.abc import Generator

    from python_discovery import PythonInfo


class RustPython(  # simplint: ignore[init-module-content]  # preserve class __module__
    ViaGlobalRefVirtualenvBuiltin, Python3Supports, ABC
):
    """Base for the built-in creators of RustPython interpreters."""

    @classmethod
    def can_describe(cls, interpreter: PythonInfo) -> bool:
        """Accept RustPython interpreters that the base describer also accepts.

        :param interpreter: the host interpreter to check

        :returns: ``True`` if this creator can describe the interpreter

        """
        return interpreter.implementation == "RustPython" and super().can_describe(interpreter)

    @classmethod
    def _executables(cls, interpreter: PythonInfo) -> Generator[tuple[Path, list[str], RefMust, RefWhen], None, None]:
        host = Path(interpreter.system_exe)
        yield host, sorted(f"{name}{cls.suffix}" for name in cls.exe_names(interpreter)), RefMust.NA, RefWhen.ANY

    @classmethod
    def exe_names(cls, interpreter: PythonInfo) -> set[str]:
        """The executable names of RustPython environments, the stem and the ``python`` variants.

        :param interpreter: the host interpreter

        :returns: the executable names without suffix

        """
        return {
            cls.exe_stem(),
            "python",
            f"python{interpreter.version_info.major}",
            f"python{interpreter.version_info.major}.{interpreter.version_info.minor}",
        }

    @classmethod
    def exe_stem(cls) -> str:
        """The executable name of RustPython environments, ``rustpython``.

        :returns: the executable stem

        """
        return "rustpython"


class RustPythonPosix(RustPython, PosixSupports):  # simplint: ignore[init-module-content]  # preserve class __module__
    """RustPython on POSIX."""


class RustPythonWindows(  # simplint: ignore[init-module-content]  # preserve class __module__
    RustPython, WindowsSupports
):
    """RustPython on Windows."""


__all__ = [
    "RustPythonPosix",
    "RustPythonWindows",
]
