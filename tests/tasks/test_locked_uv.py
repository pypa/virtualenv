from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Final

from tasks import locked_uv


def test_locked_uv_reports_the_pinned_version(tmp_path: Path) -> None:
    lock: Final[Path] = tmp_path / "pylock.toml"
    lock.write_text('[[packages]]\nname = "uv"\nversion = "0.13.4"\n', encoding="utf-8")
    result: Final[subprocess.CompletedProcess[str]] = subprocess.run(
        [sys.executable, str(Path(locked_uv.__file__).resolve())],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=tmp_path,
    )
    assert result.returncode == 0
    assert result.stdout == "version=0.13.4\n"
