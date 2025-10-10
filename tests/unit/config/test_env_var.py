from __future__ import annotations

import os
from pathlib import Path

import pytest

from virtualenv.config.cli.parser import VirtualEnvOptions
from virtualenv.config.ini import IniConfig
from virtualenv.create.via_global_ref.builtin.cpython.common import is_macos_brew
from virtualenv.discovery.py_info import PythonInfo
from virtualenv.run import session_via_cli


@pytest.fixture
def _empty_conf(tmp_path, monkeypatch):
    conf = tmp_path / "conf.ini"
    monkeypatch.setenv(IniConfig.VIRTUALENV_CONFIG_FILE_ENV_VAR, str(conf))
    conf.write_text("[virtualenv]", encoding="utf-8")


@pytest.mark.usefixtures("_empty_conf")
def test_value_ok(monkeypatch):
    monkeypatch.setenv("VIRTUALENV_VERBOSE", "5")
    result = session_via_cli(["venv"])
    assert result.verbosity == 5


@pytest.mark.usefixtures("_empty_conf")
def test_value_bad(monkeypatch, caplog):
    monkeypatch.setenv("VIRTUALENV_VERBOSE", "a")
    result = session_via_cli(["venv"])
    assert result.verbosity == 2
    assert len(caplog.messages) == 1
    assert "env var VIRTUALENV_VERBOSE failed to convert" in caplog.messages[0]
    assert "invalid literal" in caplog.messages[0]


def test_python_via_env_var(monkeypatch):
    options = VirtualEnvOptions()
    monkeypatch.setenv("VIRTUALENV_PYTHON", "python3")
    session_via_cli(["venv"], options=options)
    assert options.python == ["python3"]


def test_python_multi_value_via_env_var(monkeypatch):
    options = VirtualEnvOptions()
    monkeypatch.setenv("VIRTUALENV_PYTHON", "python3,python2")
    session_via_cli(["venv"], options=options)
    assert options.python == ["python3", "python2"]


def test_python_multi_value_newline_via_env_var(monkeypatch):
    options = VirtualEnvOptions()
    monkeypatch.setenv("VIRTUALENV_PYTHON", "python3\npython2")
    session_via_cli(["venv"], options=options)
    assert options.python == ["python3", "python2"]


def test_python_multi_value_prefer_newline_via_env_var(monkeypatch):
    options = VirtualEnvOptions()
    monkeypatch.setenv("VIRTUALENV_PYTHON", "python3\npython2,python27")
    session_via_cli(["venv"], options=options)
    assert options.python == ["python3", "python2,python27"]


def test_extra_search_dir_via_env_var(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    value = f"a{os.linesep}0{os.linesep}b{os.pathsep}c"
    monkeypatch.setenv("VIRTUALENV_EXTRA_SEARCH_DIR", str(value))
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    (tmp_path / "c").mkdir()
    result = session_via_cli(["venv"])
    assert result.seeder.extra_search_dir == [Path("a").resolve(), Path("b").resolve(), Path("c").resolve()]


@pytest.mark.usefixtures("_empty_conf")
@pytest.mark.skipif(is_macos_brew(PythonInfo.current_system()), reason="no copy on brew")
def test_value_alias(monkeypatch, mocker):
    from virtualenv.config.cli.parser import VirtualEnvConfigParser  # noqa: PLC0415

    prev = VirtualEnvConfigParser._fix_default  # noqa: SLF001

    def func(self, action):
        if action.dest == "symlinks":
            action.default = True  # force symlink to be true
        elif action.dest == "copies":
            action.default = False  # force default copy to be False, we expect env-var to flip it
        return prev(self, action)

    mocker.patch("virtualenv.run.VirtualEnvConfigParser._fix_default", side_effect=func, autospec=True)

    monkeypatch.delenv("SYMLINKS", raising=False)
    monkeypatch.delenv("VIRTUALENV_COPIES", raising=False)
    monkeypatch.setenv("VIRTUALENV_ALWAYS_COPY", "1")
    result = session_via_cli(["venv"])
    assert result.creator.symlinks is False
