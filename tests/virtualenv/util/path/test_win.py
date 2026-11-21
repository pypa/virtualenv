from __future__ import annotations

import os
from stat import S_IREAD
from typing import TYPE_CHECKING, Final

import pytest

from virtualenv.info import fs_supports_symlink

if os.name == "nt":
    from virtualenv.util.path._win import delete_readonly  # ruff:ignore[import-private-name]  # paired test

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.skipif(os.name != "nt" or not fs_supports_symlink(), reason="Windows file links")
def test_delete_readonly_refuses_reparse_points(tmp_path: Path) -> None:
    source: Final[Path] = tmp_path / "source"
    source.write_bytes(b"unchanged")
    source.chmod(S_IREAD)
    link: Final[Path] = tmp_path / "link"
    link.symlink_to(source)
    with pytest.raises(OSError, match="refusing to change attributes"):
        delete_readonly(str(link))
    assert (link.is_symlink(), source.read_bytes(), bool(source.stat().st_file_attributes & 1)) == (
        True,
        b"unchanged",
        True,
    )
