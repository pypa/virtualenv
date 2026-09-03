from __future__ import annotations

import codecs
import logging
import sys
from textwrap import dedent

import pytest

from virtualenv.config.ini import IniConfig
from virtualenv.info import IS_PYPY, IS_WIN, fs_supports_symlink
from virtualenv.run import session_via_cli


@pytest.mark.skipif(not fs_supports_symlink(), reason="symlink is not supported")
@pytest.mark.xfail(
    # https://doc.pypy.org/en/latest/install.html?highlight=symlink#download-a-pre-built-pypy
    IS_PYPY and IS_WIN and sys.version_info[0:2] >= (3, 9),
    reason="symlink is not supported",
)
def test_ini_can_be_overwritten_by_flag(tmp_path, monkeypatch) -> None:
    custom_ini = tmp_path / "conf.ini"
    custom_ini.write_text(
        dedent(
            """
        [virtualenv]
        copies = True
        """,
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("VIRTUALENV_CONFIG_FILE", str(custom_ini))

    result = session_via_cli(["venv", "--symlinks"])

    symlinks = result.creator.symlinks
    assert symlinks is True


def test_ini_that_fails_to_parse_is_ignored(tmp_path, caplog) -> None:
    bad_ini = tmp_path / "conf.ini"
    bad_ini.write_text("this line has no section header\n", encoding="utf-8")

    config = IniConfig(env={"VIRTUALENV_CONFIG_FILE": str(bad_ini)})

    assert bool(config) is False
    assert config.has_virtualenv_section is False
    assert "failed to parse" in config.epilog
    assert any("failed to read config file" in r.message for r in caplog.records if r.levelno == logging.ERROR)


def test_ini_that_fails_to_parse_does_not_break_the_cli(tmp_path, monkeypatch) -> None:
    bad_ini = tmp_path / "conf.ini"
    bad_ini.write_text("this line has no section header\n", encoding="utf-8")
    monkeypatch.setenv("VIRTUALENV_CONFIG_FILE", str(bad_ini))

    result = session_via_cli(["venv"])  # the config is ignored, defaults apply

    assert result.creator.clear is False


def test_ini_with_utf8_bom_is_read(tmp_path, monkeypatch) -> None:
    custom_ini = tmp_path / "conf.ini"
    content = dedent(
        """
        [virtualenv]
        clear = True
        """,
    )
    custom_ini.write_bytes(codecs.BOM_UTF8 + content.encode("utf-8"))  # how Notepad and PowerShell 5 write UTF-8
    monkeypatch.setenv("VIRTUALENV_CONFIG_FILE", str(custom_ini))

    result = session_via_cli(["venv"])

    assert result.creator.clear is True
