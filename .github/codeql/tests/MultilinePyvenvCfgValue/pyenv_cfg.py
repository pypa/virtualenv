from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


class RawPyEnvCfg:
    def __init__(self, content: dict[str, str], path: Path) -> None:
        self.content = content
        self.path = path

    def write(self) -> None:
        write_file(self.path, "".join(f"{key} = {value}\n" for key, value in self.content.items()).encode("utf-8"))


def write_file(path: Path, data: bytes) -> None:
    path.write_bytes(data)


class CollapsedPyEnvCfg:
    def __init__(self, content: dict[str, str], path: Path) -> None:
        self.content = content
        self.path = path

    def write(self) -> None:
        text = "".join(
            f"{collapse_line_boundaries(key)} = {collapse_line_boundaries(value)}\n"
            for key, value in self.content.items()
        )
        write_file(self.path, text.encode("utf-8"))


def collapse_line_boundaries(text: str) -> str:
    return " ".join(text.splitlines())
