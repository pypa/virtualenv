from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from pathlib import Path


class Cache(Protocol):
    """A protocol for a cache."""

    def get(self, path: Path) -> Any: ...

    def set(self, path: Path, data: Any) -> None: ...

    def remove(self, path: Path) -> None: ...

    def clear(self) -> None: ...
