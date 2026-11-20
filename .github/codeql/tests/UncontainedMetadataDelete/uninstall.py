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
        resolved = entry.resolve()
        if root not in resolved.parents:
            continue
        safe_delete(resolved)
    for name in (dist / "RECORD").read_text(encoding="utf-8").splitlines():
        entry = dist.parent / name.split(",")[0]
        resolved = entry.resolve()
        if root in resolved.parents:
            resolved.unlink()
            remove_file(resolved)


def uninstall_wrong_guard(dist: Path, env_dir: Path) -> None:
    root: Final = env_dir.resolve()
    for name in (dist / "top_level.txt").read_text(encoding="utf-8").splitlines():
        entry = dist.parent / name
        resolved = entry.resolve()
        if root not in entry.parents:
            continue
        safe_delete(resolved)


def uninstall_wrong_delete(dist: Path, env_dir: Path) -> None:
    root: Final = env_dir.resolve()
    for name in (dist / "top_level.txt").read_text(encoding="utf-8").splitlines():
        entry = dist.parent / name
        if root not in entry.resolve().parents:
            continue
        safe_delete(entry)
