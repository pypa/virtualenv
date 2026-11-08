from __future__ import annotations

import logging
import os
from collections import OrderedDict
from typing import TYPE_CHECKING, Final

from virtualenv.util.path import write_file
from virtualenv.util.text import collapse_line_boundaries

if TYPE_CHECKING:
    from pathlib import Path

#: Logger of this module.
LOGGER: Final[logging.Logger] = logging.getLogger(__name__)

# a plain value such as 3.14 or true would otherwise turn into a path whenever the working directory has an entry so
# named
_PATH_KEYS: Final[frozenset[str]] = frozenset({
    "home",
    "executable",
    "base-prefix",
    "base-exec-prefix",
    "base-executable",
    "venvlauncher_command",
})


class PyEnvCfg:
    """The ``pyvenv.cfg`` file of an environment, read into ordered key-value pairs.

    :param content: the key-value pairs in file order
    :param path: the location of the file

    """

    def __init__(self, content: OrderedDict[str, str], path: Path) -> None:
        self.content = content
        self.path = path

    @classmethod
    def from_folder(cls, folder: Path) -> PyEnvCfg:
        """Load the ``pyvenv.cfg`` of the environment in the given folder.

        :param folder: the environment folder

        :returns: the parsed configuration, empty when the file does not exist

        """
        return cls.from_file(folder / "pyvenv.cfg")

    @classmethod
    def from_file(cls, path: Path) -> PyEnvCfg:
        """Load the ``pyvenv.cfg`` at the given path.

        :param path: the location of the file

        :returns: the parsed configuration, empty when the file does not exist

        """
        return PyEnvCfg(cls._read_values(path) if path.exists() else OrderedDict(), path)

    @staticmethod
    def _read_values(path: Path) -> OrderedDict[str, str]:
        _validate_path(path)
        content = OrderedDict()
        for line in path.read_text(encoding="utf-8").splitlines():
            key, separator, value = line.partition("=")
            if not separator or (key := key.strip()).startswith("#"):
                continue
            value = value.strip()
            if len(value) > 1 and value[0] in {"'", '"'} and value[0] == value[-1]:
                value = value[1:-1]
            content[key] = value
        return content

    def __setitem__(self, key: str, value: str) -> None:
        self.content[key] = value

    def __getitem__(self, key: str) -> str:
        return self.content[key]

    def __contains__(self, item: str) -> bool:
        return item in self.content

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(path={self.path})"

    def write(self) -> None:
        """Write the key-value pairs to the file, quoting the prompt and absolutizing existing paths."""
        _validate_path(self.path)
        LOGGER.debug("write %s", self.path)
        text = ""
        for key, value in self.content.items():
            if key == "prompt" and value:
                normalized_value = f'"{value}"'
            elif key in _PATH_KEYS and os.path.exists(value):
                # abspath rather than realpath keeps symlinked prefixes intact, as venv does (#2770)
                normalized_value = os.path.abspath(value)
            else:
                normalized_value = value
            line = f"{collapse_line_boundaries(key)} = {collapse_line_boundaries(normalized_value)}"
            LOGGER.debug("\t%r", line)
            text += line
            text += "\n"
        write_file(self.path, text.encode("utf-8"))

    def refresh(self) -> OrderedDict[str, str]:
        """Re-read the key-value pairs from the file, discarding in-memory changes.

        :returns: the key-value pairs read from the file

        """
        self.content = self._read_values(self.path)
        return self.content

    def update(self, other: dict[str, str]) -> PyEnvCfg:
        """Merge the given pairs into the configuration.

        :param other: the key-value pairs to add or overwrite

        :returns: this configuration, to allow chaining

        """
        self.content.update(other)
        return self


def _validate_path(path: Path) -> None:
    if path.exists() and not path.is_file():
        msg = f"configuration path is not a regular file: {path}"
        raise ValueError(msg)


__all__ = [
    "LOGGER",
    "PyEnvCfg",
]
