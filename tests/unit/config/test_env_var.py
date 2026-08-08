from __future__ import annotations

import os
from pathlib import Path

import pytest
from python_discovery import PythonInfo

from virtualenv.config.cli.parser import VirtualEnvOptions
from virtualenv.config.convert import ListType
from virtualenv.config.ini import IniConfig
from virtualenv.create.via_global_ref.builtin.cpython.common import is_macos_brew
from virtualenv.run import session_via_cli


@pytest.fixture
def _empty_conf(tmp_path, monkeypatch) -> None:
    conf = tmp_path / "conf.ini"
    monkeypatch.setenv(IniConfig.VIRTUALENV_CONFIG_FILE_ENV_VAR, str(conf))
    conf.write_text("[virtualenv]", encoding="utf-8")


@pytest.mark.usefixtures("_empty_conf")
def test_value_ok(monkeypatch) -> None:
    monkeypatch.setenv("VIRTUALENV_VERBOSE", "5")
    result = session_via_cli(["venv"])
    assert result.verbosity == 5


@pytest.mark.usefixtures("_empty_conf")
def test_value_bad(monkeypatch, caplog) -> None:
    monkeypatch.setenv("VIRTUALENV_VERBOSE", "a")
    result = session_via_cli(["venv"])
    assert result.verbosity == 2
    assert len(caplog.messages) == 1
    assert "env var VIRTUALENV_VERBOSE failed to convert" in caplog.messages[0]
    assert "invalid literal" in caplog.messages[0]


def test_python_via_env_var(monkeypatch) -> None:
    options = VirtualEnvOptions()
    monkeypatch.setenv("VIRTUALENV_PYTHON", "python3")
    session_via_cli(["venv"], options=options)
    assert options.python == ["python3"]


def test_python_multi_value_via_env_var(monkeypatch) -> None:
    options = VirtualEnvOptions()
    monkeypatch.setenv("VIRTUALENV_PYTHON", "python3,python2")
    session_via_cli(["venv"], options=options)
    assert options.python == ["python3", "python2"]


def test_python_multi_value_newline_via_env_var(monkeypatch) -> None:
    options = VirtualEnvOptions()
    monkeypatch.setenv("VIRTUALENV_PYTHON", "python3\npython2")
    session_via_cli(["venv"], options=options)
    assert options.python == ["python3", "python2"]


def test_python_multi_value_prefer_newline_via_env_var(monkeypatch) -> None:
    options = VirtualEnvOptions()
    monkeypatch.setenv("VIRTUALENV_PYTHON", "python3\npython2,python27")
    session_via_cli(["venv"], options=options)
    assert options.python == ["python3", "python2,python27"]


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        pytest.param("a,b,c", ["a", "b", "c"], id="comma"),
        pytest.param("a\nb\nc", ["a", "b", "c"], id="newline"),
        pytest.param("a\nb,c", ["a", "b,c"], id="newline_wins_over_comma"),
        pytest.param(" a , b ", ["a", "b"], id="strips_whitespace"),
        pytest.param("a\n\nb", ["a", "b"], id="drops_blank_lines"),
        pytest.param("a", ["a"], id="single"),
        pytest.param("", [], id="empty"),
        pytest.param(b"a,b", ["a", "b"], id="bytes_comma"),
        pytest.param(b"a\nb", ["a", "b"], id="bytes_newline"),
        pytest.param(["a", "b"], ["a", "b"], id="list_passthrough"),
    ],
)
def test_split_values(value, expected) -> None:
    assert ListType(list, str).split_values(value) == expected


def test_extra_search_dir_via_env_var(tmp_path, monkeypatch) -> None:
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
def test_value_alias(monkeypatch, mocker) -> None:
    from virtualenv.config.cli.parser import VirtualEnvConfigParser  # ruff:ignore[import-outside-top-level]

    prev = VirtualEnvConfigParser._fix_default  # ruff:ignore[private-member-access]

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
