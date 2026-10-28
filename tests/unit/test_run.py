from __future__ import annotations

import logging
import re
import shutil
import sys
from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING, Final

import pytest

from virtualenv import __version__
from virtualenv.app_data import AppDataDiskFolder, ReadOnlyAppData
from virtualenv.config.cli.parser import VirtualEnvOptions
from virtualenv.run import cli_run, session_via_cli

if TYPE_CHECKING:
    from collections.abc import Callable

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


def test_read_only_app_data_ignores_missing_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, give_app_data: Callable[[Path], list[str]]
) -> None:
    cache: Final = tmp_path / "cache"
    session_via_cli(["--app-data", str(cache), str(tmp_path / "warm")])  # discovery cannot fill a read-only cache
    monkeypatch.setenv("VIRTUALENV_OVERRIDE_APP_DATA", str(tmp_path / "default"))
    options: Final = VirtualEnvOptions()
    session_via_cli(["--read-only-app-data", *give_app_data(cache), str(tmp_path / "env")], options)
    assert (type(options.app_data), str(options.app_data)) == (ReadOnlyAppData, str(cache))


@pytest.mark.parametrize(
    "prepare_default",
    [
        pytest.param(lambda _: None, id="missing"),
        # a file in the way makes the default fall back to temporary app-data
        pytest.param(Path.touch, id="blocked"),
    ],
)
def test_given_app_data_leaves_default_alone(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    give_app_data: Callable[[Path], list[str]],
    prepare_default: Callable[[Path], None],
) -> None:
    default_folder: Final = tmp_path / "default"
    prepare_default(default_folder)
    monkeypatch.setenv("VIRTUALENV_OVERRIDE_APP_DATA", str(default_folder / "cache"))
    cache: Final = tmp_path / "cache"
    options: Final = VirtualEnvOptions()
    session_via_cli([*give_app_data(cache), str(tmp_path / "env")], options)
    assert (type(options.app_data), str(options.app_data), (default_folder / "cache").exists()) == (
        AppDataDiskFolder,
        str(cache),
        False,
    )


def test_read_only_app_data_rejects_missing_given_folder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, give_app_data: Callable[[Path], list[str]]
) -> None:
    (tmp_path / "default").mkdir()
    monkeypatch.setenv("VIRTUALENV_OVERRIDE_APP_DATA", str(tmp_path / "default"))
    cache: Final = tmp_path / "cache"
    args: Final = ["--read-only-app-data", *give_app_data(cache), str(tmp_path / "env")]
    with pytest.raises(RuntimeError, match=rf"^read-only app data directory {re.escape(str(cache))} does not exist$"):
        session_via_cli(args)


def test_help_shows_default_app_data(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("COLUMNS", "1000")
    monkeypatch.setenv("VIRTUALENV_OVERRIDE_APP_DATA", str(tmp_path))
    with pytest.raises(SystemExit) as context:
        cli_run(args=["--help"])
    assert (
        context.value.code,
        f"a data folder used as cache by the virtualenv (default: {tmp_path})" in capsys.readouterr().out,
    ) == (0, True)


def _on_command_line(_: pytest.MonkeyPatch, folder: Path) -> list[str]:
    return ["--app-data", str(folder)]


def _in_environment(monkeypatch: pytest.MonkeyPatch, folder: Path) -> list[str]:
    monkeypatch.setenv("VIRTUALENV_APP_DATA", str(folder))
    return []


def _in_config_file(monkeypatch: pytest.MonkeyPatch, folder: Path) -> list[str]:
    (ini := folder.parent / "virtualenv.ini").write_text(f"[virtualenv]\napp_data = {folder}\n", encoding="utf-8")
    monkeypatch.setenv("VIRTUALENV_CONFIG_FILE", str(ini))
    return []


@pytest.fixture(
    params=[
        pytest.param(_on_command_line, id="cli"),
        pytest.param(_in_environment, id="env-var"),
        pytest.param(_in_config_file, id="ini"),
    ]
)
def give_app_data(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> Callable[[Path], list[str]]:
    return partial(request.param, monkeypatch)


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
