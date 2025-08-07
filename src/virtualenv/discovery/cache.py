from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from typing_extensions import Self


class Cache(ABC):
    """A generic cache interface."""

    @abstractmethod
    def get(self, key: str) -> Any | None:
        """
        Get a value from the cache.

        :param key: the key to retrieve
        :return: the cached value, or None if not found
        """
        raise NotImplementedError

    @abstractmethod
    def set(self, key: str, value: Any) -> None:
        """
        Set a value in the cache.

        :param key: the key to set
        :param value: the value to cache
        """
        raise NotImplementedError

    @abstractmethod
    def remove(self, key: str) -> None:
        """
        Remove a value from the cache.

        :param key: the key to remove
        """
        raise NotImplementedError

    @abstractmethod
    def clear(self) -> None:
        """Clear the entire cache."""
        raise NotImplementedError

    def __enter__(self) -> Self:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    def close(self) -> None:  # noqa: B027
        """
        Close the cache, releasing any resources.

        This is a no-op by default but can be overridden in subclasses.
        """


__all__ = [
    "Cache",
]
