from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING, Any, ContextManager

if TYPE_CHECKING:
    from pathlib import Path


class MockAppData:
    def __init__(self, readonly: bool = False) -> None:
        self.readonly = readonly
        self._py_info_clear_called = 0
        self._py_info_map: dict[Path, Any] = {}

    def py_info(self, path: Path) -> Any:
        return self._py_info_map.get(path)

    def py_info_clear(self) -> None:
        self._py_info_clear_called += 1

    @contextmanager
    def ensure_extracted(self, path: Path, to_folder: Path | None = None) -> ContextManager[Path]:  # noqa: ARG002
        yield path

    @contextmanager
    def extract(self, path: Path, to_folder: Path | None = None) -> ContextManager[Path]:  # noqa: ARG002
        yield path

    def close(self) -> None:
        pass


class MockCache:
    def __init__(self) -> None:
        self._cache: dict[Path, Any] = {}
        self._clear_called = 0

    def get(self, path: Path) -> Any:
        return self._cache.get(path)

    def set(self, path: Path, data: Any) -> None:
        self._cache[path] = data

    def remove(self, path: Path) -> None:
        if path in self._cache:
            del self._cache[path]

    def clear(self) -> None:
        self._clear_called += 1
        self._cache.clear()
