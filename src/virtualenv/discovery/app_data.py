from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING, Any, ContextManager, Protocol

if TYPE_CHECKING:
    from pathlib import Path


class AppData(Protocol):
    """Protocol for application data store."""

    def py_info(self, path: Path) -> Any: ...

    def py_info_clear(self) -> None: ...

    @contextmanager
    def ensure_extracted(self, path: Path, to_folder: Path | None = None) -> ContextManager[Path]: ...

    @contextmanager
    def extract(self, path: Path, to_folder: Path | None = None) -> ContextManager[Path]: ...

    def close(self) -> None: ...
