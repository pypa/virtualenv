from __future__ import annotations

import zipfile
from typing import TYPE_CHECKING

import pytest

from virtualenv.seed.embed.via_app_data.pip_install._safe_extract_zip import extract_zip  # ruff:ignore[import-private-name]  # paired test  # fmt: skip

if TYPE_CHECKING:
    from pathlib import Path


def test_safe_extract_zip_allows_normal_entry(tmp_path: Path) -> None:
    archive = tmp_path / "ok.zip"
    _write_zip_with_entry(archive, "pkg/inner.txt")
    target = tmp_path / "out"
    target.mkdir()

    with zipfile.ZipFile(str(archive)) as zip_ref:
        extract_zip(zip_ref, target)

    assert (target / "pkg" / "inner.txt").read_text(encoding="utf-8") == "payload"


def _write_zip_with_entry(zip_path: Path, entry_name: str) -> None:
    with zipfile.ZipFile(str(zip_path), "w") as archive:
        archive.writestr(entry_name, "payload")


def test_safe_extract_zip_rejects_parent_traversal(tmp_path: Path) -> None:
    archive = tmp_path / "evil.zip"
    _write_zip_with_entry(archive, "../escape.txt")
    target = tmp_path / "out"
    target.mkdir()

    with zipfile.ZipFile(str(archive)) as zip_ref, pytest.raises(RuntimeError, match="escaping target directory"):
        extract_zip(zip_ref, target)

    assert not (tmp_path / "escape.txt").exists()


@pytest.mark.parametrize(
    "entry",
    [
        pytest.param("/tmp/evil.txt", id="posix"),  # ruff:ignore[hardcoded-temp-file]  # literal hostile archive entry
        pytest.param("C:/Windows/System32/evil.txt", id="windows"),
    ],
)
def test_safe_extract_zip_rejects_absolute_entry(tmp_path: Path, entry: str) -> None:
    archive = tmp_path / "abs.zip"
    _write_zip_with_entry(archive, entry)
    target = tmp_path / "out"
    target.mkdir()

    with zipfile.ZipFile(str(archive)) as zip_ref, pytest.raises(RuntimeError, match="absolute path"):
        extract_zip(zip_ref, target)
