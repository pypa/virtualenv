from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import TYPE_CHECKING

from virtualenv.app_data.na import AppDataDisabled
from virtualenv.discovery.cache import Cache

if TYPE_CHECKING:
    from virtualenv.app_data.base import AppData

LOGGER = logging.getLogger(__name__)


class FileCache(Cache):
    def __init__(self, app_data: AppData) -> None:
        self.app_data = app_data if app_data is not None else AppDataDisabled()

    def get(self, key: Path):
        """Get a value from the file cache."""
        py_info, py_info_store = None, self.app_data.py_info(key)
        with py_info_store.locked():
            if py_info_store.exists():
                py_info = self._read_from_store(py_info_store, key)
        return py_info

    def set(self, key: Path, value: dict) -> None:
        """Set a value in the file cache."""
        py_info_store = self.app_data.py_info(key)
        with py_info_store.locked():
            path_text = str(key)
            try:
                path_modified = key.stat().st_mtime
            except OSError:
                path_modified = -1

            py_info_script = Path(__file__).parent / "py_info.py"
            try:
                py_info_hash = hashlib.sha256(py_info_script.read_bytes()).hexdigest()
            except OSError:
                py_info_hash = None

            data = {
                "st_mtime": path_modified,
                "path": path_text,
                "content": value,
                "hash": py_info_hash,
            }
            py_info_store.write(data)

    def remove(self, key: Path) -> None:
        """Remove a value from the file cache."""
        py_info_store = self.app_data.py_info(key)
        with py_info_store.locked():
            if py_info_store.exists():
                py_info_store.remove()

    def clear(self) -> None:
        """Clear the entire file cache."""
        self.app_data.py_info_clear()

    def _read_from_store(self, py_info_store, path: Path):
        data = py_info_store.read()
        path_text = str(path)
        try:
            path_modified = path.stat().st_mtime
        except OSError:
            path_modified = -1

        py_info_script = Path(__file__).parent / "py_info.py"
        try:
            py_info_hash = hashlib.sha256(py_info_script.read_bytes()).hexdigest()
        except OSError:
            py_info_hash = None

        of_path = data.get("path")
        of_st_mtime = data.get("st_mtime")
        of_content = data.get("content")
        of_hash = data.get("hash")

        if of_path == path_text and of_st_mtime == path_modified and of_hash == py_info_hash:
            return of_content

        py_info_store.remove()
        return None


__all__ = [
    "FileCache",
]
