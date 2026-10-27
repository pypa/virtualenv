from __future__ import annotations

import sys
from pathlib import Path
from typing import Final

import tomllib


def main() -> None:
    packages: Final[list[dict[str, str]]] = tomllib.loads(Path("pylock.toml").read_text(encoding="utf-8"))["packages"]
    version: Final[str] = next(package["version"] for package in packages if package["name"] == "uv")
    sys.stdout.write(f"version={version}\n")


if __name__ == "__main__":
    main()


__all__ = [
    "main",
]
