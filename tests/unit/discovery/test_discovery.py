from __future__ import annotations

import logging
import os
import subprocess
import sys
from argparse import Namespace
from pathlib import Path

import pytest
from python_discovery import PythonInfo

from virtualenv.discovery.builtin import Builtin, get_interpreter
from virtualenv.info import IS_WIN


def test_relative_path(session_app_data, monkeypatch) -> None:
    sys_executable = Path(PythonInfo.current_system(session_app_data).system_executable)
    cwd = sys_executable.parents[1]
    monkeypatch.chdir(str(cwd))
    relative = str(sys_executable.relative_to(cwd))
    result = get_interpreter(relative, [], session_app_data)
    assert result is not None


def test_discovery_fallback_fail(session_app_data, caplog) -> None:
    caplog.set_level(logging.DEBUG)
    builtin = Builtin(
        Namespace(app_data=session_app_data, try_first_with=[], python=["magic-one", "magic-two"], env=os.environ),
    )

    result = builtin.run()
    assert result is None

    assert "accepted" not in caplog.text


def test_discovery_fallback_ok(session_app_data, caplog) -> None:
    caplog.set_level(logging.DEBUG)
    builtin = Builtin(
        Namespace(app_data=session_app_data, try_first_with=[], python=["magic-one", sys.executable], env=os.environ),
    )

    result = builtin.run()
    assert result is not None, caplog.text
    assert result.executable == sys.executable, caplog.text

    assert "accepted" in caplog.text


@pytest.fixture
def mock_get_interpreter(mocker):
    return mocker.patch(
        "virtualenv.discovery.builtin.get_interpreter",
        lambda key, *_args, **_kwargs: getattr(mocker.sentinel, key),
    )


@pytest.mark.usefixtures("mock_get_interpreter")
def test_returns_first_python_specified_when_only_env_var_one_is_specified(
    mocker, monkeypatch, session_app_data
) -> None:
    monkeypatch.setenv("VIRTUALENV_PYTHON", "python_from_env_var")
    builtin = Builtin(
        Namespace(app_data=session_app_data, try_first_with=[], python=["python_from_env_var"], env=os.environ),
    )

    result = builtin.run()

    assert result == mocker.sentinel.python_from_env_var


@pytest.mark.usefixtures("mock_get_interpreter")
def test_returns_second_python_specified_when_more_than_one_is_specified_and_env_var_is_specified(
    mocker, monkeypatch, session_app_data
) -> None:
    monkeypatch.setenv("VIRTUALENV_PYTHON", "python_from_env_var")
    builtin = Builtin(
        Namespace(
            app_data=session_app_data,
            try_first_with=[],
            python=["python_from_env_var", "python_from_cli"],
            env=os.environ,
        ),
    )

    result = builtin.run()

    assert result == mocker.sentinel.python_from_cli


def test_discovery_absolute_path_with_try_first(tmp_path, session_app_data) -> None:
    good_env = tmp_path / "good"
    bad_env = tmp_path / "bad"

    subprocess.check_call([sys.executable, "-m", "virtualenv", str(good_env)])
    subprocess.check_call([sys.executable, "-m", "virtualenv", str(bad_env)])

    scripts_dir = "Scripts" if IS_WIN else "bin"
    exe_name = "python.exe" if IS_WIN else "python"
    good_exe = good_env / scripts_dir / exe_name
    bad_exe = bad_env / scripts_dir / exe_name

    interpreter = get_interpreter(
        str(good_exe),
        try_first_with=[str(bad_exe)],
        app_data=session_app_data,
    )

    assert interpreter is not None
    assert Path(interpreter.executable) == good_exe


def test_absolute_path_does_not_exist(tmp_path) -> None:
    """Test that virtualenv does not fail when an absolute path that does not exist is provided."""
    command = [
        sys.executable,
        "-m",
        "virtualenv",
        "-p",
        "/this/path/does/not/exist",
        "-p",
        sys.executable,
        str(tmp_path / "dest"),
    ]

    process = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
        encoding="utf-8",
    )

    assert process.returncode == 0, process.stderr


def test_absolute_path_does_not_exist_fails(tmp_path) -> None:
    """Test that virtualenv fails when a single absolute path that does not exist is provided."""
    command = [
        sys.executable,
        "-m",
        "virtualenv",
        "-p",
        "/this/path/does/not/exist",
        str(tmp_path / "dest"),
    ]

    process = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
        encoding="utf-8",
    )

    assert process.returncode != 0, process.stderr


@pytest.mark.usefixtures("mock_get_interpreter")
def test_returns_first_python_specified_when_no_env_var_is_specified(mocker, monkeypatch, session_app_data) -> None:
    monkeypatch.delenv("VIRTUALENV_PYTHON", raising=False)
    builtin = Builtin(
        Namespace(app_data=session_app_data, try_first_with=[], python=["python_from_cli"], env=os.environ),
    )

    result = builtin.run()

    assert result == mocker.sentinel.python_from_cli


def test_discovery_via_version_specifier(session_app_data) -> None:
    """Test that version specifiers like >=3.11 work correctly through the virtualenv wrapper."""
    current = PythonInfo.current_system(session_app_data)
    major, minor = current.version_info.major, current.version_info.minor

    spec = f">={major}.{minor}"
    interpreter = get_interpreter(spec, [], session_app_data)
    assert interpreter is not None
    assert interpreter.version_info.major == major
    assert interpreter.version_info.minor >= minor

    spec = f">={major}.{minor},<{major}.{minor + 10}"
    interpreter = get_interpreter(spec, [], session_app_data)
    assert interpreter is not None
    assert interpreter.version_info.major == major
    assert minor <= interpreter.version_info.minor < minor + 10

    spec = f"cpython>={major}.{minor}"
    interpreter = get_interpreter(spec, [], session_app_data)
    if current.implementation == "CPython":
        assert interpreter is not None
        assert interpreter.implementation == "CPython"


def test_invalid_discovery_via_env_var(monkeypatch, tmp_path) -> None:
    """When VIRTUALENV_DISCOVERY is set to an unavailable plugin, raise a clear error instead of KeyError."""
    monkeypatch.setenv("VIRTUALENV_DISCOVERY", "nonexistent_plugin")
    process = subprocess.run(
        [sys.executable, "-m", "virtualenv", str(tmp_path / "env")],
        capture_output=True,
        text=True,
        check=False,
        encoding="utf-8",
    )
    assert process.returncode != 0
    output = process.stdout + process.stderr
    assert "nonexistent_plugin" in output
    assert "is not available" in output
    assert "KeyError" not in output


def test_invalid_discovery_via_env_var_unit(monkeypatch) -> None:
    """Unit test: get_discover raises RuntimeError with helpful message for unknown discovery method."""
    from virtualenv.config.cli.parser import VirtualEnvConfigParser  # noqa: PLC0415
    from virtualenv.run.plugin.discovery import get_discover  # noqa: PLC0415

    monkeypatch.setenv("VIRTUALENV_DISCOVERY", "nonexistent_plugin")
    parser = VirtualEnvConfigParser()
    with pytest.raises(RuntimeError, match=r"nonexistent_plugin.*is not available"):
        get_discover(parser, [])
