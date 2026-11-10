from __future__ import annotations

import shutil
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from pathlib import Path


def safe_delete(dest: Path) -> None:
    shutil.rmtree(dest)


def remove_file(path: Path) -> None:
    path.unlink()


def uninstall_unchecked(dist: Path) -> None:
    for name in (dist / "top_level.txt").read_text(encoding="utf-8").splitlines():
        safe_delete(dist.parent / name)
    for name in (i.split(",")[0] for i in (dist / "RECORD").read_text(encoding="utf-8").splitlines()):
        (dist.parent / name).unlink()
        remove_file(dist.parent / name)


def uninstall_contained(dist: Path, env_dir: Path) -> None:
    root: Final = env_dir.resolve()
    for name in (dist / "top_level.txt").read_text(encoding="utf-8").splitlines():
        entry = dist.parent / name
        if root not in entry.resolve().parents:
            continue
        safe_delete(entry)
    for name in (dist / "RECORD").read_text(encoding="utf-8").splitlines():
        entry = dist.parent / name.split(",")[0]
        if root in entry.resolve().parents:
            entry.unlink()
            remove_file(entry)
