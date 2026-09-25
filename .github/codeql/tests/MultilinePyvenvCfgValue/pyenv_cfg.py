from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


def collapse_line_boundaries(text: str) -> str:
    return " ".join(text.splitlines())


class RawPyEnvCfg:
    def __init__(self, content: dict[str, str], path: Path) -> None:
        self.content = content
        self.path = path

    def write(self) -> None:
        text = "".join(f"{key} = {value}\n" for key, value in self.content.items())
        self.path.write_text(text, encoding="utf-8")


class CollapsedPyEnvCfg:
    def __init__(self, content: dict[str, str], path: Path) -> None:
        self.content = content
        self.path = path

    def write(self) -> None:
        text = "".join(
            f"{collapse_line_boundaries(key)} = {collapse_line_boundaries(value)}\n"
            for key, value in self.content.items()
        )
        self.path.write_text(text, encoding="utf-8")
