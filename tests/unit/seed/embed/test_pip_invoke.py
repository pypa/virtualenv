from __future__ import annotations

import os
import subprocess
from typing import TYPE_CHECKING, Final

import pytest

from virtualenv.run import cli_run

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.parametrize("safe_path", [pytest.param("", id="default"), pytest.param("1", id="safe-path")])
def test_pip_invoke_uses_selected_wheel(
    tmp_path: Path, current_fastest: str, monkeypatch: pytest.MonkeyPatch, safe_path: str
) -> None:
    monkeypatch.setenv("PYTHONSAFEPATH", safe_path)
    (tmp_path / "pip").mkdir()
    (tmp_path / "pip" / "__init__.py").write_text("raise SystemExit('imported from the working directory')", "utf-8")
    monkeypatch.chdir(tmp_path)
    session: Final = cli_run([
        str(tmp_path / "env"),
        "--creator",
        current_fastest,
        "--seeder",
        "pip",
        "--pip",
        "embed",
        "--no-periodic-update",
    ])
    result: Final = subprocess.run(
        [str(session.creator.exe), "-I", "-m", "pip", "--version"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    assert os.path.normcase(str(session.creator.purelib)) in os.path.normcase(result.stdout)


@pytest.mark.parametrize(
    "excluded",
    [pytest.param("pip", id="no-pip"), pytest.param("setuptools", id="no-setuptools"), pytest.param("", id="all")],
)
def test_base_bootstrap_via_pip_invoke(tmp_path: Path, current_fastest: str, excluded: str) -> None:
    command: Final = [
        "--seeder",
        "pip",
        str(tmp_path / "env"),
        "--download",
        "--creator",
        current_fastest,
        "--pip",
        "embed",
        "--setuptools",
        "embed",
        "--no-periodic-update",
    ]
    if excluded:
        command.append(f"--no-{excluded}")
    session: Final = cli_run(command)
    assert {path.name for path in session.creator.purelib.iterdir()} & {"pip", "setuptools"} == {
        "pip",
        "setuptools",
    } - {excluded}


def test_pip_invoke_reports_unavailable_wheel(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="could not get wheel for distribution pip"):
        cli_run([
            str(tmp_path / "env"),
            "--seeder",
            "pip",
            "--pip",
            "0.0.0",
            "--no-download",
            "--no-periodic-update",
        ])
