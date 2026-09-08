from __future__ import annotations

import codecs
import logging
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Final, cast

import pytest

from virtualenv.config.ini import IniConfig
from virtualenv.info import IS_PYPY, IS_WIN, fs_supports_symlink
from virtualenv.run import session_via_cli

if TYPE_CHECKING:
    from pytest_mock import MockerFixture

    from virtualenv.create.via_global_ref.api import ViaGlobalRefApi


@pytest.mark.skipif(not fs_supports_symlink(), reason="symlink is not supported")
@pytest.mark.xfail(
    # https://doc.pypy.org/en/latest/install.html?highlight=symlink#download-a-pre-built-pypy
    IS_PYPY and IS_WIN and sys.version_info[0:2] >= (3, 9),
    reason="symlink is not supported",
)
def test_ini_can_be_overwritten_by_flag(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    custom_ini: Final[Path] = tmp_path / "conf.ini"
    custom_ini.write_text("[virtualenv]\ncopies = True\n", encoding="utf-8")
    monkeypatch.setenv("VIRTUALENV_CONFIG_FILE", str(custom_ini))

    assert cast("ViaGlobalRefApi", session_via_cli(["venv", "--symlinks"]).creator).symlinks is True


def test_ini_that_fails_to_parse_is_ignored(invalid_ini: Path) -> None:
    config: Final[IniConfig] = IniConfig(env={"VIRTUALENV_CONFIG_FILE": str(invalid_ini)})
    assert (bool(config), config.has_virtualenv_section) == (False, False)


def test_ini_that_fails_to_parse_is_reported(invalid_ini: Path) -> None:
    config: Final[IniConfig] = IniConfig(env={"VIRTUALENV_CONFIG_FILE": str(invalid_ini)})
    assert config.epilog == (
        f"\nconfig file {invalid_ini.resolve()} failed to parse (changed via env var VIRTUALENV_CONFIG_FILE)"
    )


def test_ini_that_fails_to_parse_is_logged(invalid_ini: Path, caplog: pytest.LogCaptureFixture) -> None:
    IniConfig(env={"VIRTUALENV_CONFIG_FILE": str(invalid_ini)})
    assert [(record.levelno, record.message.split(" because ")[0]) for record in caplog.records] == [
        (logging.ERROR, f"failed to read config file {invalid_ini}")
    ]


def test_ini_that_fails_to_parse_does_not_break_the_cli(invalid_ini: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VIRTUALENV_CONFIG_FILE", str(invalid_ini))

    assert session_via_cli(["venv"]).creator.clear is False


@pytest.fixture(
    params=[
        pytest.param(b"no section header\n", id="missing-header"),
        pytest.param(b"[virtualenv]\nclear = True\ninvalid\n", id="partial-parse"),
        pytest.param(b"[virtualenv]\nclear = True\nclear = False\n", id="duplicate-option"),
        pytest.param(b"[virtualenv]\nclear = True\n[virtualenv]\n", id="duplicate-section"),
        pytest.param(b"[virtualenv]\nclear = True\n\xff", id="invalid-utf8"),
    ]
)
def invalid_ini(tmp_path: Path, request: pytest.FixtureRequest) -> Path:
    config_file: Final[Path] = tmp_path / "conf.ini"
    config_file.write_bytes(request.param)
    return config_file


@pytest.mark.parametrize(
    "method",
    [pytest.param("exists", id="stat"), pytest.param("resolve", id="resolve"), pytest.param("open", id="read")],
)
def test_ini_filesystem_error_is_ignored(tmp_path: Path, mocker: MockerFixture, method: str) -> None:
    config_file: Final[Path] = tmp_path / "conf.ini"
    config_file.write_text("[virtualenv]\nclear = True\n", encoding="utf-8")
    mocker.patch.object(Path, method, autospec=True, side_effect=PermissionError("access denied"))

    config: Final[IniConfig] = IniConfig(env={"VIRTUALENV_CONFIG_FILE": str(config_file)})

    assert (bool(config), config.has_config_file, config.has_virtualenv_section) == (False, None, False)


@pytest.mark.parametrize("prefix", [pytest.param(b"", id="utf8"), pytest.param(codecs.BOM_UTF8, id="utf8-bom")])
def test_ini_utf8_is_read(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, prefix: bytes) -> None:
    config_file: Final[Path] = tmp_path / "conf.ini"
    config_file.write_bytes(prefix + b"[virtualenv]\nclear = True\n")
    monkeypatch.setenv("VIRTUALENV_CONFIG_FILE", str(config_file))

    assert session_via_cli(["venv"]).creator.clear is True
