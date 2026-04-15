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

    def __init__(self) -> None:
        pass

    error = RuntimeError("no app data folder available, probably no write access to the folder")

    def close(self) -> None:
        """Do nothing."""

    def reset(self) -> None:
        """Do nothing."""

    def py_info(self, path: Path) -> ContentStoreNA:  # noqa: ARG002
        return ContentStoreNA()

    def embed_update_log(self, distribution: str, for_py_version: str) -> ContentStoreNA:  # noqa: ARG002
        return ContentStoreNA()

    def extract(self, path: Path, to_folder: Path | None) -> NoReturn:  # noqa: ARG002
        raise self.error

    @contextmanager
    def locked(self, path: Path) -> Generator[None]:  # noqa: ARG002
        """Do nothing."""
        yield

    @property
    def house(self) -> NoReturn:
        raise self.error

    def wheel_image(self, for_py_version: str, name: str) -> NoReturn:  # noqa: ARG002
        raise self.error

    def py_info_clear(self) -> None:
        """Nothing to clear."""


class ContentStoreNA(ContentStore):
    def exists(self) -> bool:
        return False

    def read(self) -> None:
        """Nothing to read."""
        return

    def write(self, content: Any) -> None:  # noqa: ANN401
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
