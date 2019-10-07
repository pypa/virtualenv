from __future__ import absolute_import, unicode_literals

import pytest

from virtualenv.config.cli import parse_core_cli
from virtualenv.interpreters.create.impl.cpython.cpython3 import CPython3Posix
from virtualenv.interpreters.discovery import CURRENT


def parse_cli(args):
    return parse_core_cli(args, CPython3Posix, CURRENT)


@pytest.fixture()
def empty_conf(tmp_path, monkeypatch):
    conf = tmp_path / "conf.ini"
    monkeypatch.setenv(str("VIRTUALENV_CONFIG_FILE"), str(conf))
    conf.write_text("[virtualenv]")


def test_value_ok(tmp_path, monkeypatch, empty_conf):
    monkeypatch.setenv(str("VIRTUALENV_VERBOSE"), str("5"))
    result = parse_cli([str(tmp_path)])
    assert result.verbose == 5


def _exc(of):
    try:
        int(of)
    except ValueError as exception:
        return exception


def test_value_bad(tmp_path, monkeypatch, caplog, empty_conf):
    monkeypatch.setenv(str("VIRTUALENV_VERBOSE"), str("a"))
    result = parse_cli([str(tmp_path)])
    assert result.verbose == 3
    msg = "env var VIRTUALENV_VERBOSE failed to convert 'a' as {!r} because {!r}".format(int, _exc("a"))
    # one for the core parse, one for the normal one
    assert caplog.messages == [msg, msg], "{}{}".format(caplog.text, msg)
