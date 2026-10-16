from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import pytest

from virtualenv import __version__
from virtualenv.run import cli_run, session_via_cli

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.parametrize(
    "option",
    [
        pytest.param(option, id=option.removeprefix("--"))
        for option in ("--prompt", "--activators", "--pip", "--setuptools")
    ],
)
def test_missing_option_value_does_not_create_app_data(tmp_path: Path, option: str) -> None:
    with pytest.raises(SystemExit) as error:
        session_via_cli([option, "--app-data", str(tmp_path / "cache"), str(tmp_path / "env")])
    assert error.value.code == 2
    assert not (tmp_path / "cache").exists()


def test_help(capsys) -> None:
    with pytest.raises(SystemExit) as context:
        cli_run(args=["-h", "-vvv"])
    assert context.value.code == 0

    out, err = capsys.readouterr()
    assert not err
    assert out


def test_version(capsys) -> None:
    with pytest.raises(SystemExit) as context:
        cli_run(args=["--version"])
    assert context.value.code == 0

    content, err = capsys.readouterr()
    assert not err

    assert __version__ in content
    import virtualenv  # ruff:ignore[import-outside-top-level]

    assert virtualenv.__file__ in content.replace("\n", "")


@pytest.mark.parametrize("on", [True, False])
def test_logging_setup(caplog, on) -> None:
    caplog.set_level(logging.DEBUG)
    session_via_cli(["env"], setup_logging=on)
    # DEBUG only level output is generated during this phase, default output is WARN, so if on no records should be
    if on:
        assert not caplog.records
    else:
        assert caplog.records


def test_invalid_discovery_method_via_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VIRTUALENV_DISCOVERY", "pyenv")
    with pytest.raises(RuntimeError, match=r"discovery 'pyenv' is not available") as exc_info:
        session_via_cli(["env"])

    error_message = str(exc_info.value)
    assert "discovery 'pyenv' is not available" in error_message
    assert "Available discovery methods:" in error_message
    assert "builtin" in error_message
    assert "Is the plugin installed?" in error_message
