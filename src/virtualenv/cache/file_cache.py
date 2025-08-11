from __future__ import annotations

from typing import TYPE_CHECKING

from virtualenv.app_data.na import AppDataDisabled
from virtualenv.cache import Cache

if TYPE_CHECKING:
    from pathlib import Path

    from virtualenv.app_data.base import AppData


class FileCache(Cache):
    def __init__(self, app_data: AppData) -> None:
        self.app_data = app_data if app_data is not None else AppDataDisabled()

    def get(self, key: Path) -> dict | None:
        """Get a value from the file cache."""
        py_info, py_info_store = None, self.app_data.py_info(key)
        with py_info_store.locked():
            if py_info_store.exists():
                py_info = py_info_store.read()
        return py_info

    def set(self, key: Path, value: dict) -> None:
        """Set a value in the file cache."""
        py_info_store = self.app_data.py_info(key)
        with py_info_store.locked():
            py_info_store.write(value)

    def remove(self, key: Path) -> None:
        """Remove a value from the file cache."""
        py_info_store = self.app_data.py_info(key)
        with py_info_store.locked():
            if py_info_store.exists():
                py_info_store.remove()

    def clear(self) -> None:
        """Clear the entire file cache."""
        self.app_data.py_info_clear()


__all__ = [
    "FileCache",
]
