from __future__ import annotations

import logging
import shutil
import sys
from typing import TYPE_CHECKING, Final

import pytest

from virtualenv import __version__
from virtualenv.run import cli_run, session_via_cli

if TYPE_CHECKING:
    from pathlib import Path

    from pytest_mock import MockerFixture


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


@pytest.mark.parametrize("option", [pytest.param("--prompt", id="prompt"), pytest.param("--pip", id="pip")])
def test_missing_option_value_precedes_interpreter_query(tmp_path: Path, option: str, mocker: MockerFixture) -> None:
    executable: Final = tmp_path / "python"
    shutil.copy2(sys.executable, executable)
    process: Final = mocker.patch(
        "python_discovery._cached_py_info.Popen", autospec=True, side_effect=AssertionError("interpreter query started")
    )
    with pytest.raises(SystemExit) as context:
        session_via_cli([option, "--python", str(executable), str(tmp_path / "env")])
    assert context.value.code == 2
    process.assert_not_called()


@pytest.mark.parametrize(
    ("leading", "trailing"),
    [
        pytest.param([], ["--no-periodic-update", "-p", sys.executable], id="nox"),
        pytest.param(["--prompt=env", f"--python={sys.executable}"], [], id="pipenv"),
    ],
)
def test_component_option_before_discovery_option(tmp_path: Path, leading: list[str], trailing: list[str]) -> None:
    session: Final = session_via_cli([*leading, str(tmp_path / "env"), *trailing])
    assert session.creator.dest == tmp_path / "env"
