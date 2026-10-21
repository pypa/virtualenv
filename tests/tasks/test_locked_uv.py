from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from textwrap import dedent
from typing import Final

import pytest

from tasks import locked_uv


def test_locked_uv_reports_the_pinned_version(tmp_path: Path) -> None:
    lock: Final[Path] = tmp_path / "pylock.toml"
    lock.write_text('[[packages]]\nname = "uv"\nversion = "0.13.4"\n', encoding="utf-8")
    result: Final[subprocess.CompletedProcess[str]] = subprocess.run(
        [sys.executable, str(Path(locked_uv.__file__).resolve()), str(lock)],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert result.returncode == 0
    assert result.stdout == "0.13.4\n"


@pytest.mark.parametrize(
    "contents",
    [
        "packages = []\n",
        dedent(
            """\
            [[packages]]
            name = "uv"
            version = "0.13.4"
            [[packages]]
            name = "uv"
            version = "0.14.0"
            """
        ),
    ],
    ids=["missing", "ambiguous"],
)
def test_locked_uv_rejects_an_unusable_lock(contents: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    lock: Final[Path] = tmp_path / "pylock.toml"
    lock.write_text(contents, encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["locked_uv.py", str(lock)])
    with pytest.raises(SystemExit) as error:
        locked_uv.main()
    assert error.value.code == "pylock.toml must pin one uv version"
