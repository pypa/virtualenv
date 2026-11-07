from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from python_discovery import PythonInfo

    from .api import ViaGlobalRefMeta


def handle_store_python(meta: ViaGlobalRefMeta, interpreter: PythonInfo) -> ViaGlobalRefMeta:
    if is_store_python(interpreter):
        meta.symlink_error = "Windows Store Python does not support virtual environments via symlink"
    return meta


def is_store_python(interpreter: PythonInfo) -> bool:
    parts = Path(interpreter.system_exe).parts
    return (
        # a Windows Store path has at least four parts, so shorter paths cannot match
        len(parts) > 4  # ruff:ignore[magic-value-comparison]
        and parts[-4] == "Microsoft"
        and parts[-3] == "WindowsApps"
        and parts[-2].startswith("PythonSoftwareFoundation.Python.3.")
        and parts[-1].startswith("python")
    )


__all__ = [
    "handle_store_python",
    "is_store_python",
]
