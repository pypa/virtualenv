from __future__ import annotations

import logging
import os
from stat import S_IREAD, S_IWRITE
from threading import Thread
from typing import TYPE_CHECKING

import pytest

from virtualenv.run import cli_run

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def envs_file(tmp_path: Path) -> Path:
    return tmp_path / ".python-envs"


@pytest.mark.parametrize(
    ("before", "after"),
    [
        pytest.param(None, "env\n", id="no-file-yet"),
        pytest.param("other\n/opt/elsewhere\n", "other\n/opt/elsewhere\nenv\n", id="appended-last"),
        pytest.param("env\nother\n", "other\nenv\n", id="relative-entry-moved-last"),
        pytest.param("{dest}\nother\n", "other\nenv\n", id="absolute-entry-moved-last"),
        pytest.param("other\r\n\r\n   \r\n", "other\nenv\n", id="blank-lines-dropped"),
    ],
)
def test_python_envs_recorded(tmp_path: Path, envs_file: Path, before: str | None, after: str) -> None:
    dest = tmp_path / "env"
    if before is not None:
        envs_file.write_bytes(before.format(dest=dest.resolve()).encode("utf-8"))
    _create(dest)
    assert envs_file.read_text(encoding="utf-8") == after


def _create(dest: Path, *args: str) -> None:
    cli_run([str(dest), "--without-pip", "--activators", "", *args], setup_logging=False)


@pytest.mark.parametrize(
    ("name", "args"),
    [
        pytest.param("env", ("--no-python-envs",), id="opted-out"),
        pytest.param(".venv", (), id="dot-venv-is-implicit"),
    ],
)
def test_python_envs_not_recorded(tmp_path: Path, envs_file: Path, name: str, args: tuple[str, ...]) -> None:
    _create(tmp_path / name, *args)
    assert not envs_file.exists()


def test_python_envs_records_parallel_creations(tmp_path: Path, envs_file: Path) -> None:
    names = [f"env-{i}" for i in range(8)]
    threads = [Thread(target=_create, args=(tmp_path / i,)) for i in names]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert sorted(envs_file.read_text(encoding="utf-8").splitlines()) == names


def test_python_envs_dot_venv_keeps_precedence(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    _create(tmp_path / ".venv")
    with caplog.at_level(logging.DEBUG):
        _create(tmp_path / "env")
    assert ".venv keeps being the default environment" in caplog.text


def test_python_envs_not_write_able(tmp_path: Path, envs_file: Path, caplog: pytest.LogCaptureFixture) -> None:
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        pytest.skip("root may write read-only files")

    envs_file.write_text("other\n", encoding="utf-8")
    envs_file.chmod(S_IREAD)
    try:
        with caplog.at_level(logging.WARNING):
            _create(tmp_path / "env")
    finally:
        envs_file.chmod(S_IREAD | S_IWRITE)
    assert f"could not record {(tmp_path / 'env').resolve()} within {envs_file.resolve()}" in caplog.text
    assert (tmp_path / "env" / "pyvenv.cfg").exists()
