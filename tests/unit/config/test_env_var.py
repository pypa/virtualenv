from __future__ import absolute_import, unicode_literals

import os
from argparse import Namespace

import pytest

from virtualenv.config.ini import IniConfig
from virtualenv.run import session_via_cli
from virtualenv.util.path import Path


def parse_cli(args):
    options = Namespace()
    return session_via_cli(args, options)


@pytest.fixture()
def empty_conf(tmp_path, monkeypatch):
    conf = tmp_path / "conf.ini"
    monkeypatch.setenv(IniConfig.VIRTUALENV_CONFIG_FILE_ENV_VAR, str(conf))
    conf.write_text("[virtualenv]")


def test_value_ok(monkeypatch, empty_conf):
    monkeypatch.setenv(str("VIRTUALENV_VERBOSE"), str("5"))
    result = parse_cli(["venv"])
    assert result.verbosity == 5


def test_value_bad(monkeypatch, caplog, empty_conf):
    monkeypatch.setenv(str("VIRTUALENV_VERBOSE"), str("a"))
    result = parse_cli(["venv"])
    assert result.verbosity == 2
    assert len(caplog.messages) == 1
    assert "env var VIRTUALENV_VERBOSE failed to convert" in caplog.messages[0]
    assert "invalid literal" in caplog.messages[0]


def test_extra_search_dir(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    value = "a{}0{}b{}c".format(os.linesep, os.linesep, os.pathsep)
    monkeypatch.setenv("VIRTUALENV_EXTRA_SEARCH_DIR", value)
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    (tmp_path / "c").mkdir()
    result = parse_cli(["venv"])
    assert result.seeder.extra_search_dir == [Path("a").resolve(), Path("b").resolve(), Path("c").resolve()]
