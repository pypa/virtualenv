from __future__ import annotations

import logging
import os
import platform
import sys
import tempfile
from typing import Final

IMPLEMENTATION: Final[str] = platform.python_implementation()
IS_PYPY: Final[bool] = IMPLEMENTATION == "PyPy"
IS_GRAALPY: Final[bool] = IMPLEMENTATION == "GraalVM"
IS_RUSTPYTHON: Final[bool] = IMPLEMENTATION == "RustPython"
IS_CPYTHON: Final[bool] = IMPLEMENTATION == "CPython"
IS_WIN: Final[bool] = sys.platform == "win32"
IS_MAC_ARM64: Final[bool] = sys.platform == "darwin" and platform.machine() == "arm64"
ROOT: Final[str] = os.path.realpath(os.path.join(os.path.abspath(__file__), os.path.pardir, os.path.pardir))
IS_ZIPAPP: Final[bool] = os.path.isfile(ROOT)
_CAN_SYMLINK = _FS_CASE_SENSITIVE = None
LOGGER: Final[logging.Logger] = logging.getLogger(__name__)


def fs_supports_symlink() -> bool:
    global _CAN_SYMLINK  # ruff:ignore[global-statement]  # a module-level cache, filled on first use

    if _CAN_SYMLINK is None:
        can = False
        if hasattr(os, "symlink"):
            # Creating a symlink can fail for a variety of reasons, indicating that the filesystem does not support it.
            # E.g. on Linux with a VFAT partition mounted.
            with tempfile.NamedTemporaryFile(prefix="TmP") as tmp_file:
                dest = os.path.join(os.path.dirname(tmp_file.name), f"{tmp_file.name}-{'b'}")
                try:
                    os.symlink(tmp_file.name, dest)
                    can = True
                except (OSError, NotImplementedError):
                    pass  # symlink is not supported
                finally:
                    if os.path.lexists(dest):
                        os.remove(dest)
            LOGGER.debug("symlink on filesystem does%s work", "" if can else " not")
        _CAN_SYMLINK = can
    return _CAN_SYMLINK


def fs_path_id(path: str) -> str:
    return path.casefold() if fs_is_case_sensitive() else path


def fs_is_case_sensitive() -> bool:
    global _FS_CASE_SENSITIVE  # ruff:ignore[global-statement]  # a module-level cache, filled on first use

    if _FS_CASE_SENSITIVE is None:
        with tempfile.NamedTemporaryFile(prefix="TmP") as tmp_file:
            _FS_CASE_SENSITIVE = not os.path.exists(tmp_file.name.lower())
            LOGGER.debug("filesystem is %scase-sensitive", "" if _FS_CASE_SENSITIVE else "not ")
    return _FS_CASE_SENSITIVE


__all__ = [
    "IS_CPYTHON",
    "IS_GRAALPY",
    "IS_MAC_ARM64",
    "IS_PYPY",
    "IS_RUSTPYTHON",
    "IS_WIN",
    "IS_ZIPAPP",
    "ROOT",
    "fs_is_case_sensitive",
    "fs_path_id",
    "fs_supports_symlink",
]
