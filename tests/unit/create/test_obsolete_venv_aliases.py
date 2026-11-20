from __future__ import annotations

import os
import shutil
import sys
from typing import TYPE_CHECKING, Final

import pytest
from python_discovery import PythonInfo

from virtualenv.info import IS_PYPY
from virtualenv.run import cli_run

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.skipif(os.name != "posix" or not PythonInfo.current_system().has_venv, reason="requires POSIX venv")
@pytest.mark.parametrize(
    ("previous", "filename", "reported"),
    [
        pytest.param(("CPython", "3.8"), "python3.8", ["python3.8"], id="cpython"),
        pytest.param(("CPython", "3.8"), "user-tool", [], id="unrelated"),
        pytest.param(("CPython", "3.8"), "python3.80", [], id="different-version"),
        pytest.param(("PyPy", "3.8"), "pypy3.8", ["pypy3.8"], id="pypy-versioned"),
        pytest.param(("PyPy", "3.8"), "libpypy3.8-c.so", ["libpypy3.8-c.so"], id="pypy-library"),
        pytest.param(
            ("PyPy", "3.8"), "pypy", ["pypy"], marks=pytest.mark.skipif(IS_PYPY, reason="alias in use"), id="pypy"
        ),
        pytest.param(("CPython", f"{sys.version_info.major}.{sys.version_info.minor}"), "user-tool", [], id="same"),
    ],
)
def test_recreate_preserves_old_alias(
    tmp_path: Path, caplog: pytest.LogCaptureFixture, previous: tuple[str, str], filename: str, reported: list[str]
) -> None:
    destination: Final[Path] = tmp_path / "env"
    bin_dir: Final[Path] = destination / "bin"
    bin_dir.mkdir(parents=True)
    (destination / "pyvenv.cfg").write_text(
        f"implementation = {previous[0]}\nversion = {previous[1]}.1\n", encoding="utf-8"
    )
    alias: Final[Path] = bin_dir / filename
    alias.write_bytes(b"existing file")
    cli_run([str(destination), "--creator", "venv", "--no-seed"], setup_logging=False)
    warnings = [message for message in caplog.messages if "files named for the previous interpreter" in message]
    assert (warnings, alias.read_bytes()) == (
        [
            f"files named for the previous interpreter remain in {str(bin_dir)!r} and may no longer work: "
            f"{name!r}. Use a fresh destination to avoid stale files."
            for name in reported
        ],
        b"existing file",
    )


@pytest.mark.skipif(
    sys.platform != "linux"
    or sys.implementation.name != "cpython"
    or sys.version_info[:2] == (3, 12)
    or not shutil.which("python3.12"),
    reason="requires Linux with Python 3.12 alongside a different CPython version",
)
def test_switch_copied_python(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    destination: Final[Path] = tmp_path / "env"
    args: Final[list[str]] = [str(destination), "--creator", "venv", "--copies", "--no-seed", "-p"]
    cli_run([*args, "python3.12"], setup_logging=False)
    alias: Final[Path] = destination / "bin" / "python3.12"
    contents = alias.read_bytes()
    cli_run([*args, sys.executable], setup_logging=False)
    assert (alias.read_bytes(), "'python3.12'. Use a fresh destination" in caplog.text) == (contents, True)
