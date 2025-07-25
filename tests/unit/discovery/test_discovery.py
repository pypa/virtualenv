from __future__ import annotations

import logging
import os
import subprocess
import sys
from argparse import Namespace
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

import pytest

from virtualenv.discovery.builtin import Builtin, get_interpreter
from virtualenv.discovery.py_info import PythonInfo
from virtualenv.info import fs_supports_symlink


@pytest.mark.skipif(not fs_supports_symlink(), reason="symlink not supported")
@pytest.mark.parametrize("case", ["mixed", "lower", "upper"])
@pytest.mark.parametrize("specificity", ["more", "less", "none"])
def test_discovery_via_path(monkeypatch, case, specificity, tmp_path, caplog, session_app_data):  # noqa: PLR0913
    caplog.set_level(logging.DEBUG)
    current = PythonInfo.current_system(session_app_data)
    name = "somethingVeryCryptic"
    threaded = "t" if current.free_threaded else ""
    if case == "lower":
        name = name.lower()
    elif case == "upper":
        name = name.upper()
    if specificity == "more":
        # e.g. spec: python3, exe: /bin/python3.12
        core_ver = current.version_info.major
        exe_ver = ".".join(str(i) for i in current.version_info[0:2]) + threaded
    elif specificity == "less":
        # e.g. spec: python3.12.1, exe: /bin/python3
        core_ver = ".".join(str(i) for i in current.version_info[0:3])
        exe_ver = current.version_info.major
    elif specificity == "none":
        # e.g. spec: python3.12.1, exe: /bin/python
        core_ver = ".".join(str(i) for i in current.version_info[0:3])
        exe_ver = ""
    core = "" if specificity == "none" else f"{name}{core_ver}{threaded}"
    exe_name = f"{name}{exe_ver}{'.exe' if sys.platform == 'win32' else ''}"
    target = tmp_path / current.install_path("scripts")
    target.mkdir(parents=True)
    executable = target / exe_name
    os.symlink(sys.executable, str(executable))
    pyvenv_cfg = Path(sys.executable).parents[1] / "pyvenv.cfg"
    if pyvenv_cfg.exists():
        (target / pyvenv_cfg.name).write_bytes(pyvenv_cfg.read_bytes())
    new_path = os.pathsep.join([str(target), *os.environ.get("PATH", "").split(os.pathsep)])
    monkeypatch.setenv("PATH", new_path)
    interpreter = get_interpreter(core, [])

    assert interpreter is not None


def test_discovery_via_path_not_found(tmp_path, monkeypatch):
    monkeypatch.setenv("PATH", str(tmp_path))
    interpreter = get_interpreter(uuid4().hex, [])
    assert interpreter is None


def test_discovery_via_path_in_nonbrowseable_directory(tmp_path, monkeypatch):
    bad_perm = tmp_path / "bad_perm"
    bad_perm.mkdir(mode=0o000)
    # path entry is unreadable
    monkeypatch.setenv("PATH", str(bad_perm))
    interpreter = get_interpreter(uuid4().hex, [])
    assert interpreter is None
    # path entry parent is unreadable
    monkeypatch.setenv("PATH", str(bad_perm / "bin"))
    interpreter = get_interpreter(uuid4().hex, [])
    assert interpreter is None


def test_relative_path(session_app_data, monkeypatch):
    sys_executable = Path(PythonInfo.current_system(app_data=session_app_data).system_executable)
    cwd = sys_executable.parents[1]
    monkeypatch.chdir(str(cwd))
    relative = str(sys_executable.relative_to(cwd))
    result = get_interpreter(relative, [], session_app_data)
    assert result is not None


def test_uv_python(monkeypatch, tmp_path_factory, mocker):
    monkeypatch.delenv("UV_PYTHON_INSTALL_DIR", raising=False)
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    monkeypatch.setenv("PATH", "")
    mocker.patch.object(PythonInfo, "satisfies", return_value=False)

    # UV_PYTHON_INSTALL_DIR
    uv_python_install_dir = tmp_path_factory.mktemp("uv_python_install_dir")
    with patch("virtualenv.discovery.builtin.PathPythonInfo.from_exe") as mock_from_exe, monkeypatch.context() as m:
        m.setenv("UV_PYTHON_INSTALL_DIR", str(uv_python_install_dir))

        get_interpreter("python", [])
        mock_from_exe.assert_not_called()

        bin_path = uv_python_install_dir.joinpath("some-py-impl", "bin")
        bin_path.mkdir(parents=True)
        bin_path.joinpath("python").touch()
        get_interpreter("python", [])
        mock_from_exe.assert_called_once()
        assert mock_from_exe.call_args[0][0] == str(bin_path / "python")

    # XDG_DATA_HOME
    xdg_data_home = tmp_path_factory.mktemp("xdg_data_home")
    with patch("virtualenv.discovery.builtin.PathPythonInfo.from_exe") as mock_from_exe, monkeypatch.context() as m:
        m.setenv("XDG_DATA_HOME", str(xdg_data_home))

        get_interpreter("python", [])
        mock_from_exe.assert_not_called()

        bin_path = xdg_data_home.joinpath("uv", "python", "some-py-impl", "bin")
        bin_path.mkdir(parents=True)
        bin_path.joinpath("python").touch()
        get_interpreter("python", [])
        mock_from_exe.assert_called_once()
        assert mock_from_exe.call_args[0][0] == str(bin_path / "python")

    # User data path
    user_data_path = tmp_path_factory.mktemp("user_data_path")
    with patch("virtualenv.discovery.builtin.PathPythonInfo.from_exe") as mock_from_exe, monkeypatch.context() as m:
        m.setattr("virtualenv.discovery.builtin.user_data_path", lambda x: user_data_path / x)

        get_interpreter("python", [])
        mock_from_exe.assert_not_called()

        bin_path = user_data_path.joinpath("uv", "python", "some-py-impl", "bin")
        bin_path.mkdir(parents=True)
        bin_path.joinpath("python").touch()
        get_interpreter("python", [])
        mock_from_exe.assert_called_once()
        assert mock_from_exe.call_args[0][0] == str(bin_path / "python")


def test_discovery_fallback_fail(session_app_data, caplog):
    caplog.set_level(logging.DEBUG)
    builtin = Builtin(
        Namespace(app_data=session_app_data, try_first_with=[], python=["magic-one", "magic-two"], env=os.environ),
    )

    result = builtin.run()
    assert result is None

    assert "accepted" not in caplog.text


def test_discovery_fallback_ok(session_app_data, caplog):
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
        lambda key, *args, **kwargs: getattr(mocker.sentinel, key),  # noqa: ARG005
    )


@pytest.mark.usefixtures("mock_get_interpreter")
def test_returns_first_python_specified_when_only_env_var_one_is_specified(mocker, monkeypatch, session_app_data):
    monkeypatch.setenv("VIRTUALENV_PYTHON", "python_from_env_var")
    builtin = Builtin(
        Namespace(app_data=session_app_data, try_first_with=[], python=["python_from_env_var"], env=os.environ),
    )

    result = builtin.run()

    assert result == mocker.sentinel.python_from_env_var


@pytest.mark.usefixtures("mock_get_interpreter")
def test_returns_second_python_specified_when_more_than_one_is_specified_and_env_var_is_specified(
    mocker, monkeypatch, session_app_data
):
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


def test_absolute_path_does_not_exist(tmp_path):
    """
    Test that virtualenv does not fail when an absolute path that does not exist is provided.
    """
    # Create a command that uses an absolute path that does not exist
    # and a valid python executable.
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

    # Run the command
    process = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
    )

    # Check that the command was successful
    assert process.returncode == 0, process.stderr


def test_absolute_path_does_not_exist_fails(tmp_path):
    """
    Test that virtualenv fails when a single absolute path that does not exist is provided.
    """
    # Create a command that uses an absolute path that does not exist
    command = [
        sys.executable,
        "-m",
        "virtualenv",
        "-p",
        "/this/path/does/not/exist",
        str(tmp_path / "dest"),
    ]

    # Run the command
    process = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
    )

    # Check that the command failed
    assert process.returncode != 0, process.stderr


@pytest.mark.usefixtures("mock_get_interpreter")
def test_returns_first_python_specified_when_no_env_var_is_specified(mocker, monkeypatch, session_app_data):
    monkeypatch.delenv("VIRTUALENV_PYTHON", raising=False)
    builtin = Builtin(
        Namespace(app_data=session_app_data, try_first_with=[], python=["python_from_cli"], env=os.environ),
    )

    result = builtin.run()

    assert result == mocker.sentinel.python_from_cli
