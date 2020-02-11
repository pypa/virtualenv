from __future__ import absolute_import, unicode_literals

import pytest

from virtualenv.config.ini import IniConfig
from virtualenv.run import session_via_cli


def parse_cli(args):
    return session_via_cli(args)


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
