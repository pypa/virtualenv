from __future__ import annotations

import os
from typing import TYPE_CHECKING, Final

import pytest

from virtualenv.info import fs_supports_symlink

if os.name == "nt":
    from virtualenv.util.path._win import clear_readonly  # ruff:ignore[import-private-name]  # paired test

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.skipif(os.name != "nt" or not fs_supports_symlink(), reason="Windows file links")
def test_clear_readonly_refuses_reparse_points(tmp_path: Path) -> None:
    source: Final = tmp_path / "source"
    source.touch()
    link: Final = tmp_path / "link"
    link.symlink_to(source)
    with pytest.raises(OSError, match="refusing to change attributes"):
        clear_readonly(str(link))
