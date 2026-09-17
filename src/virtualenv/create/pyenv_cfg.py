from __future__ import annotations

import logging
import os
from collections import OrderedDict
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from pathlib import Path

LOGGER = logging.getLogger(__name__)

# pyvenv.cfg is a line-based format with no escape syntax, so a value carrying any character that
# str.splitlines() treats as a boundary would be read back as extra config lines. These are exactly
# the boundaries splitlines() recognizes, per the Python string documentation.
_LINE_BOUNDARIES: Final[tuple[str, ...]] = (
    "\n",
    "\r",
    "\v",
    "\f",
    "\x1c",
    "\x1d",
    "\x1e",
    "\x85",
    chr(0x2028),  # line separator
    chr(0x2029),  # paragraph separator
)


class PyEnvCfg:
    def __init__(self, content: OrderedDict[str, str], path: Path) -> None:
        self.content = content
        self.path = path

    @classmethod
    def from_folder(cls, folder: Path) -> PyEnvCfg:
        return cls.from_file(folder / "pyvenv.cfg")

    @classmethod
    def from_file(cls, path: Path) -> PyEnvCfg:
        content = cls._read_values(path) if path.exists() else OrderedDict()
        return PyEnvCfg(content, path)

    @staticmethod
    def _read_values(path: Path) -> OrderedDict[str, str]:
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

    def write(self) -> None:
        LOGGER.debug("write %s", self.path)
        text = ""
        for key, value in self.content.items():
            # Use abspath to normalize relative paths but preserve symlinks (match venv behavior)
            # See issue #2770 - realpath resolves symlinks which breaks prefix symlinks
            if key == "prompt" and value:
                normalized_value = f'"{value}"'
            else:
                normalized_value = os.path.abspath(value) if value and os.path.exists(value) else value
            line = f"{_one_line(key)} = {_one_line(normalized_value)}"
            LOGGER.debug("\t%s", line)
            text += line
            text += "\n"
        self.path.write_text(text, encoding="utf-8")

    def refresh(self) -> OrderedDict[str, str]:
        self.content = self._read_values(self.path)
        return self.content

    def __setitem__(self, key: str, value: str) -> None:
        self.content[key] = value

    def __getitem__(self, key: str) -> str:
        return self.content[key]

    def __contains__(self, item: str) -> bool:
        return item in self.content

    def update(self, other: dict[str, str]) -> PyEnvCfg:
        self.content.update(other)
        return self

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(path={self.path})"


def _one_line(text: str) -> str:
    """Collapse line boundaries so a value can never be read back as extra config lines."""
    for boundary in _LINE_BOUNDARIES:
        text = text.replace(boundary, " ")
    return text


__all__ = [
    "PyEnvCfg",
]
