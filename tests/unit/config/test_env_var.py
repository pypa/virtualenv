from __future__ import absolute_import, unicode_literals

import os

import pytest

from virtualenv.config.ini import IniConfig
from virtualenv.run import session_via_cli
from virtualenv.util.path import Path


@pytest.fixture()
def empty_conf(tmp_path, monkeypatch):
    conf = tmp_path / "conf.ini"
    monkeypatch.setenv(IniConfig.VIRTUALENV_CONFIG_FILE_ENV_VAR, str(conf))
    conf.write_text("[virtualenv]")


def test_value_ok(monkeypatch, empty_conf):
    monkeypatch.setenv(str("VIRTUALENV_VERBOSE"), str("5"))
    result = session_via_cli(["venv"])
    assert result.verbosity == 5


def test_value_bad(monkeypatch, caplog, empty_conf):
    monkeypatch.setenv(str("VIRTUALENV_VERBOSE"), str("a"))
    result = session_via_cli(["venv"])
    assert result.verbosity == 2
    assert len(caplog.messages) == 1
    assert "env var VIRTUALENV_VERBOSE failed to convert" in caplog.messages[0]
    assert "invalid literal" in caplog.messages[0]


def test_extra_search_dir_via_env_var(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    value = "a{}0{}b{}c".format(os.linesep, os.linesep, os.pathsep)
    monkeypatch.setenv(str("VIRTUALENV_EXTRA_SEARCH_DIR"), str(value))
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    (tmp_path / "c").mkdir()
    result = session_via_cli(["venv"])
    assert result.seeder.extra_search_dir == [Path("a").resolve(), Path("b").resolve(), Path("c").resolve()]


def test_value_alias(monkeypatch, mocker, empty_conf):
    from virtualenv.config.cli.parser import VirtualEnvConfigParser

    prev = VirtualEnvConfigParser._fix_default

    def func(self, action):
        if action.dest == "symlinks":
            action.default = True  # force symlink to be true
        elif action.dest == "copies":
            action.default = False  # force default copy to be False, we expect env-var to flip it
        return prev(self, action)

    mocker.patch("virtualenv.run.VirtualEnvConfigParser._fix_default", side_effect=func, autospec=True)

    monkeypatch.delenv(str("SYMLINKS"), raising=False)
    monkeypatch.delenv(str("VIRTUALENV_COPIES"), raising=False)
    monkeypatch.setenv(str("VIRTUALENV_ALWAYS_COPY"), str("1"))
    result = session_via_cli(["venv"])
    assert result.creator.symlinks is False
