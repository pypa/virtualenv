"""Virtualenv-specific Discover base class for plugin-based Python discovery."""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from argparse import ArgumentParser
    from collections.abc import Mapping

    from python_discovery import PythonInfo

    from virtualenv.config.cli.parser import VirtualEnvOptions


class Discover(ABC):
    def __init__(self, options: VirtualEnvOptions) -> None:
        self._has_run = False
        self._interpreter: PythonInfo | None = None
        self._env: Mapping[str, str] = options.env if options.env is not None else os.environ

    @property
    def interpreter(self) -> PythonInfo | None:
        """The interpreter as returned by :meth:`run`, cached."""
        if self._has_run is False:
            self._interpreter = self.run()
            self._has_run = True
        return self._interpreter

    @abstractmethod
    def run(self) -> PythonInfo | None:
        raise NotImplementedError

    @classmethod
    def add_parser_arguments(cls, parser: ArgumentParser) -> None:
        raise NotImplementedError


__all__ = [
    "Discover",
]
