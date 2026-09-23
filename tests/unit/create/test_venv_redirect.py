from __future__ import annotations

import logging
import os
from stat import S_IREAD, S_IWRITE
from typing import TYPE_CHECKING

import pytest

from virtualenv.run import cli_run

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def redirect(tmp_path: Path) -> Path:
    return tmp_path / ".venv"


def _create(dest: Path, *args: str) -> None:
    cli_run([str(dest), "--without-pip", "--activators", "", *args], setup_logging=False)


def test_venv_redirect_points_at_created(redirect: Path) -> None:
    _create(redirect.parent / "env")

    assert redirect.read_text(encoding="utf-8") == "env\n"


@pytest.mark.parametrize(
    "line_end", [pytest.param("\n", id="lf"), pytest.param("\r\n", id="crlf"), pytest.param("", id="none")]
)
def test_venv_redirect_moves_to_newest(redirect: Path, line_end: str) -> None:
    _create(redirect.parent / "old")
    redirect.write_bytes(f"old{line_end}".encode())

    _create(redirect.parent / "new")

    assert redirect.read_text(encoding="utf-8") == "new\n"


@pytest.mark.parametrize(
    "existing",
    [
        pytest.param("missing\n", id="target-missing"),
        pytest.param("", id="empty"),
    ],
)
def test_venv_redirect_keeps_foreign(redirect: Path, existing: str) -> None:
    redirect.write_text(existing, encoding="utf-8")

    _create(redirect.parent / "env")

    assert redirect.read_text(encoding="utf-8") == existing


def test_venv_redirect_keeps_redirect_to_other_tool(redirect: Path) -> None:
    other = redirect.parent / "other"
    other.mkdir()
    (other / "pyvenv.cfg").write_text("home = /usr/bin\nuv = 0.12.5\n", encoding="utf-8")
    redirect.write_text("other\n", encoding="utf-8")

    _create(redirect.parent / "env")

    assert redirect.read_text(encoding="utf-8") == "other\n"


def test_venv_redirect_keeps_undecodable(redirect: Path) -> None:
    redirect.write_bytes(b"\xff\xfeenv\n")

    _create(redirect.parent / "env")

    assert redirect.read_bytes() == b"\xff\xfeenv\n"


def test_venv_redirect_keeps_venv_folder(redirect: Path, caplog: pytest.LogCaptureFixture) -> None:
    _create(redirect)

    with caplog.at_level(logging.DEBUG):
        _create(redirect.parent / "env")

    assert f"{redirect} keeps being the default environment" in caplog.text


def test_venv_redirect_opted_out(redirect: Path) -> None:
    _create(redirect.parent / "env", "--no-venv-redirect")

    assert not redirect.exists()


def test_venv_redirect_not_write_able(redirect: Path, caplog: pytest.LogCaptureFixture) -> None:
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        pytest.skip("root may write read-only files")
    _create(redirect.parent / "old")
    redirect.write_text("old\n", encoding="utf-8")
    redirect.chmod(S_IREAD)
    try:
        with caplog.at_level(logging.WARNING):
            _create(redirect.parent / "env")
    finally:
        redirect.chmod(S_IREAD | S_IWRITE)

    assert f"could not point {redirect.resolve()} at {(redirect.parent / 'env').resolve()}" in caplog.text
