from __future__ import absolute_import, unicode_literals

import os
from contextlib import contextmanager

import pytest

from virtualenv.config.cli.parser import VirtualEnvConfigParser
from virtualenv.config.ini import IniConfig


@pytest.fixture()
def gen_parser_no_conf_env(monkeypatch, tmp_path):
    keys_to_delete = {key for key in os.environ if key.startswith(str("VIRTUALENV_"))}
    for key in keys_to_delete:
        monkeypatch.delenv(key)
    monkeypatch.setenv(IniConfig.VIRTUALENV_CONFIG_FILE_ENV_VAR, str(tmp_path / "missing"))

    @contextmanager
    def _build():
        parser = VirtualEnvConfigParser()

        def _run(*args):
            return parser.parse_args(args=args)

        yield parser, _run
        parser.enable_help()

    return _build


def test_flag(gen_parser_no_conf_env):
    with gen_parser_no_conf_env() as (parser, run):
        parser.add_argument("--clear", dest="clear", action="store_true", help="it", default=False)
    result = run()
    assert result.clear is False
    result = run("--clear")
    assert result.clear is True
