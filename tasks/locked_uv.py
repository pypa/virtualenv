from __future__ import annotations

import sys
from pathlib import Path
from typing import Final

import tomllib


def main() -> None:
    packages: Final[list[dict[str, str]]] = tomllib.loads(Path("pylock.toml").read_text(encoding="utf-8"))["packages"]
    versions: Final[set[str]] = {package["version"] for package in packages if package["name"] == "uv"}
    if len(versions) != 1:
        msg = "pylock.toml must pin one uv version"
        raise SystemExit(msg)
    sys.stdout.write(f"{versions.pop()}\n")


if __name__ == "__main__":
    main()


__all__ = [
    "main",
]
