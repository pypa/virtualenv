from __future__ import annotations

import os
from contextlib import contextmanager

import pytest

from virtualenv.config.cli.parser import ExtendAction, VirtualEnvConfigParser, VirtualEnvOptions
from virtualenv.config.ini import IniConfig
from virtualenv.run import session_via_cli


@pytest.fixture
def gen_parser_no_conf_env(monkeypatch, tmp_path):
    keys_to_delete = {key for key in os.environ if key.startswith("VIRTUALENV_")}
    for key in keys_to_delete:
        monkeypatch.delenv(key)
    monkeypatch.setenv(IniConfig.VIRTUALENV_CONFIG_FILE_ENV_VAR, str(tmp_path / "missing"))

    @contextmanager
    def _build():
        parser = VirtualEnvConfigParser()

        def _run(*args):
            return parser.parse_args(args=args)

        try:
            yield parser, _run
        finally:
            parser.enable_help()

    return _build


def test_flag(gen_parser_no_conf_env) -> None:
    with gen_parser_no_conf_env() as (parser, run):
        parser.add_argument("--clear", dest="clear", action="store_true", help="it", default=False)
    result = run()
    assert result.clear is False
    result = run("--clear")
    assert result.clear is True


@pytest.mark.parametrize("source", ["default", "env var"])
def test_extend_action_resets_between_parses(gen_parser_no_conf_env, monkeypatch, source: str) -> None:
    if source == "env var":
        monkeypatch.setenv("VIRTUALENV_PATHS", "configured")
    with gen_parser_no_conf_env() as (parser, run):
        action = parser.add_argument(
            "--paths", action=ExtendAction, type=str, nargs="+", default=["configured"] if source == "default" else []
        )

    args = ("--paths", "first", "second", "--paths", "third")
    for _ in range(2):
        result = run(*args)
        assert result.paths == ["first", "second", "third"]
        assert result.get_source("paths") == "cli"
    assert run("--paths", "replacement").paths == ["replacement"]

    result = run()
    assert result.paths == ["configured"]
    assert result.get_source("paths") == source
    assert action.default == ["configured"]


def test_reset_app_data_does_not_conflict_clear() -> None:
    options = VirtualEnvOptions()
    session_via_cli(["--clear", "venv"], options=options)
    assert options.clear is True
    assert options.reset_app_data is False


def test_builtin_discovery_class_preferred(mocker) -> None:
    mocker.patch(
        "virtualenv.run.plugin.discovery._get_default_discovery",
        return_value=["pluginA", "pluginX", "builtin", "Aplugin", "Xplugin"],
    )

    options = VirtualEnvOptions()
    session_via_cli(["venv"], options=options)
    assert options.discovery == "builtin"
