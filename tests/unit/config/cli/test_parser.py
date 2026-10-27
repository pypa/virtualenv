from __future__ import annotations

import os
import sys
from contextlib import contextmanager
from typing import TYPE_CHECKING, Final, Protocol

import pytest

from virtualenv.config.cli.parser import ExtendAction, VirtualEnvConfigParser, VirtualEnvOptions
from virtualenv.config.ini import IniConfig
from virtualenv.run import session_via_cli

if TYPE_CHECKING:
    from argparse import Namespace
    from collections.abc import Callable, Generator
    from contextlib import AbstractContextManager
    from pathlib import Path

    class _Run(Protocol):
        def __call__(self, *args: str) -> Namespace: ...

    _GenParser = Callable[[], AbstractContextManager[tuple[VirtualEnvConfigParser, _Run]]]


@pytest.fixture
def gen_parser_no_conf_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> _GenParser:
    for key in {key for key in os.environ if key.startswith("VIRTUALENV_")}:
        monkeypatch.delenv(key)
    monkeypatch.setenv(IniConfig.VIRTUALENV_CONFIG_FILE_ENV_VAR, str(tmp_path / "missing"))

    @contextmanager
    def build() -> Generator[tuple[VirtualEnvConfigParser, _Run]]:
        parser: Final = VirtualEnvConfigParser()

        def run(*args: str) -> Namespace:
            return parser.parse_args(args=args)

        try:
            yield parser, run
        finally:
            parser.enable_help()

    return build


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


def test_accumulating_actions_reset_between_parses(
    gen_parser_no_conf_env: _GenParser, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("VIRTUALENV_SPEC", "configured")
    with gen_parser_no_conf_env() as (parser, run):
        parser.add_argument("-v", dest="verbose", action="count", default=2)
        parser.add_argument("--spec", action="append", type=str, default=[])

    for _ in range(3):
        result = run("-v", "-v", "--spec", "first")
        assert (result.verbose, result.spec) == (4, ["configured", "first"])

    result = run()
    assert (result.verbose, result.get_source("verbose"), result.spec, result.get_source("spec")) == (
        2,
        "default",
        ["configured"],
        "env var",
    )


@pytest.mark.usefixtures("gen_parser_no_conf_env")
def test_session_counts_cli_options_once(tmp_path: Path) -> None:
    options: Final = VirtualEnvOptions()
    session: Final = session_via_cli(
        ["-v", "--try-first-with", "missing", "-p", sys.executable, str(tmp_path / "venv")],
        options=options,
        setup_logging=False,
    )
    assert (session.verbosity, options.python, options.try_first_with) == (3, [sys.executable], ["missing"])


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
