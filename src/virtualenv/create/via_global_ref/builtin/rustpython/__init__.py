from __future__ import annotations

from .rustpython import RustPython as RustPython
from .rustpython import RustPythonPosix, RustPythonWindows

__all__ = [
    "RustPythonPosix",
    "RustPythonWindows",
]
