from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING

from .base import AppData, ContentStore

if TYPE_CHECKING:
    from collections.abc import Generator
    from pathlib import Path
    from typing import Any, NoReturn


class AppDataDisabled(AppData):
    """No application cache available (most likely as we don't have write permissions)."""

    transient = True
    can_update = False

    error = RuntimeError("no app data folder available, probably no write access to the folder")

    def __init__(self) -> None:
        pass

    @property
    def house(self) -> NoReturn:
        raise self.error

    def close(self) -> None:
        """Do nothing."""

    def reset(self) -> None:
        """Do nothing."""

    # the no-op store ignores the path, the signature must match the store interface
    def py_info(self, path: Path) -> ContentStoreNA:  # ruff:ignore[unused-method-argument]
        return ContentStoreNA()

    # the no-op store ignores the distribution, the signature must match the store interface
    def embed_update_log(self, distribution: str, for_py_version: str) -> ContentStoreNA:  # ruff:ignore[unused-method-argument]
        return ContentStoreNA()

    # the no-op store never extracts, so the arguments are unused
    def extract(self, path: Path, to_folder: Path | None) -> NoReturn:  # ruff:ignore[unused-method-argument]
        raise self.error

    @contextmanager
    # the no-op store takes no lock, so the path is unused
    def locked(self, path: Path) -> Generator[None]:  # ruff:ignore[unused-method-argument]
        """Do nothing."""
        yield

    # the no-op store never has an image, so the arguments are unused
    def wheel_image(self, for_py_version: str, name: str) -> NoReturn:  # ruff:ignore[unused-method-argument]
        raise self.error

    def py_info_clear(self) -> None:
        """Nothing to clear."""


class ContentStoreNA(ContentStore):
    def exists(self) -> bool:
        return False

    def read(self) -> None:
        """Nothing to read."""
        return

    # matches the base store's Any content, which this no-op store discards
    def write(self, content: Any) -> None:  # ruff:ignore[any-type]
        """Nothing to write."""

    def remove(self) -> None:
        """Nothing to remove."""

    @contextmanager
    def locked(self) -> Generator[None]:
        yield


__all__ = [
    "AppDataDisabled",
    "ContentStoreNA",
]
