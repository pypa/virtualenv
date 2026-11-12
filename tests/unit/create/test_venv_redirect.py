from __future__ import annotations

import logging
import os
from functools import partial
from stat import S_IFMT, S_IREAD, S_IWRITE
from typing import TYPE_CHECKING, Final

import pytest

from virtualenv.run import cli_run
from virtualenv.util.path import write_file

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from pytest_mock import MockerFixture


@pytest.fixture
def redirect(tmp_path: Path) -> Path:
    return tmp_path / ".venv"


@pytest.fixture
def project_redirect(redirect: Path) -> Path:
    (redirect.parent / "pyproject.toml").write_text('[project]\nname = "demo"\n', encoding="utf-8")
    return redirect


def _create(dest: Path, *args: str) -> None:
    cli_run([str(dest), "--without-pip", "--activators", "", *args], setup_logging=False)


def test_venv_redirect_auto_skips_folder_without_pyproject(redirect: Path) -> None:
    _create(redirect.parent / "env")

    assert not redirect.exists()


def test_venv_redirect_auto_keeps_existing_redirect(project_redirect: Path) -> None:
    _create(project_redirect.parent / "old")

    _create(project_redirect.parent / "new")

    assert project_redirect.read_text(encoding="utf-8") == "old\n"


def test_venv_redirect_opted_out_in_project(project_redirect: Path) -> None:
    _create(project_redirect.parent / "env", "--no-venv-redirect")

    assert not project_redirect.exists()


@pytest.mark.parametrize(
    ("env_var", "env_value", "flags", "written"),
    [
        pytest.param("VIRTUALENV_VENV_REDIRECT", "false", (), False, id="env-off"),
        pytest.param("VIRTUALENV_NO_VENV_REDIRECT", "true", (), False, id="negative-env-off"),
        pytest.param("VIRTUALENV_NO_VENV_REDIRECT", "false", (), True, id="negative-env-false-stays-auto"),
        pytest.param("VIRTUALENV_NO_VENV_REDIRECT", "true", ("--venv-redirect",), True, id="cli-on-beats-env-off"),
        pytest.param("VIRTUALENV_VENV_REDIRECT", "true", ("--no-venv-redirect",), False, id="cli-off-beats-env-on"),
    ],
)
# each parametrized case feeds one argument per field
def test_venv_redirect_env_var_and_cli(  # ruff:ignore[too-many-arguments]
    project_redirect: Path,
    monkeypatch: pytest.MonkeyPatch,
    env_var: str,
    env_value: str,
    flags: tuple[str, ...],
    written: bool,
) -> None:
    monkeypatch.setenv(env_var, env_value)

    _create(project_redirect.parent / "env", *flags)

    assert project_redirect.exists() is written


@pytest.mark.parametrize(
    ("ini", "env_vars", "written"),
    [
        pytest.param("no_venv_redirect = true", {}, False, id="ini-off"),
        pytest.param("no_venv_redirect = true", {"VIRTUALENV_VENV_REDIRECT": "true"}, True, id="env-on-beats-ini-off"),
        pytest.param("venv_redirect = true", {"VIRTUALENV_NO_VENV_REDIRECT": "true"}, False, id="env-off-beats-ini-on"),
        pytest.param(
            "", {"VIRTUALENV_VENV_REDIRECT": "1", "VIRTUALENV_NO_VENV_REDIRECT": "1"}, False, id="both-env-opt-out"
        ),
    ],
)
def test_venv_redirect_ini_and_env_var(
    project_redirect: Path, ini: str, env_vars: dict[str, str], written: bool
) -> None:
    config: Final[Path] = project_redirect.parent / "virtualenv.ini"
    config.write_text(f"[virtualenv]\n{ini}\n", encoding="utf-8")
    cli_run(
        [str(project_redirect.parent / "env"), "--without-pip", "--activators", ""],
        setup_logging=False,
        env={**os.environ, "VIRTUALENV_CONFIG_FILE": str(config), **env_vars},
    )

    assert (project_redirect.parent / "env" / "pyvenv.cfg").is_file()
    assert project_redirect.exists() is written


def test_venv_redirect_forced_points_at_created(redirect: Path) -> None:
    _create(redirect.parent / "env", "--venv-redirect")

    assert redirect.read_text(encoding="utf-8") == "env\n"


def test_venv_redirect_write_failure_does_not_abort_creation(
    redirect: Path, mocker: MockerFixture, caplog: pytest.LogCaptureFixture
) -> None:
    def fail_redirect(path: Path, data: bytes) -> None:
        if path == redirect:
            msg = "write blocked"
            raise OSError(msg)
        write_file(path, data)

    mocker.patch("virtualenv.create.creator.write_file", autospec=True, side_effect=fail_redirect)

    _create(redirect.parent / "env", "--venv-redirect")

    assert (redirect.exists(), (redirect.parent / "env" / "pyvenv.cfg").is_file()) == (False, True)
    assert f"could not point {redirect} at {redirect.parent / 'env'} - write blocked" in caplog.messages


_CONTROL_CHARACTERS: Final[tuple[int, ...]] = (10, 13, 11, 12, 28, 29, 30)
_UNREPRESENTABLE_NAMES: Final[list[pytest.ParameterSet]] = [
    *(
        pytest.param(
            f"env{chr(code)}name",
            id=f"U+{code:04X}",
            marks=pytest.mark.skipif(os.name == "nt", reason="Windows rejects control characters in directory names"),
        )
        for code in _CONTROL_CHARACTERS
    ),
    *(pytest.param(f"env{chr(code)}name", id=f"U+{code:04X}") for code in (133, 8232, 8233)),
    pytest.param(" env", id="leading-whitespace"),
    pytest.param(
        "env ",
        id="trailing-whitespace",
        marks=pytest.mark.skipif(os.name == "nt", reason="Windows strips trailing whitespace from names"),
    ),
]


@pytest.mark.parametrize("name", _UNREPRESENTABLE_NAMES)
def test_venv_redirect_skips_unrepresentable_names(project_redirect: Path, name: str) -> None:
    cli_run([
        str(project_redirect.parent / name),
        "--without-pip",
        "--activators",
        "",
        "--venv-redirect",
    ])
    assert not project_redirect.exists()


@pytest.mark.parametrize("name", _UNREPRESENTABLE_NAMES)
def test_venv_redirect_keeps_existing_for_unrepresentable_names(project_redirect: Path, name: str) -> None:
    cli_run([str(project_redirect.parent / "old"), "--without-pip", "--activators", ""])
    cli_run([
        str(project_redirect.parent / name),
        "--without-pip",
        "--activators",
        "",
        "--venv-redirect",
    ])
    assert project_redirect.read_text(encoding="utf-8") == "old\n"


@pytest.mark.parametrize(
    "line_end", [pytest.param("\n", id="lf"), pytest.param("\r\n", id="crlf"), pytest.param("", id="none")]
)
def test_venv_redirect_forced_moves_to_newest(redirect: Path, line_end: str) -> None:
    _create(redirect.parent / "old", "--venv-redirect")
    redirect.write_bytes(f"old{line_end}".encode())

    _create(redirect.parent / "new", "--venv-redirect")

    assert redirect.read_text(encoding="utf-8") == "new\n"


@pytest.mark.parametrize(
    "existing",
    [
        pytest.param("missing\n", id="target-missing"),
        pytest.param("", id="empty"),
    ],
)
def test_venv_redirect_forced_keeps_foreign(redirect: Path, existing: str) -> None:
    redirect.write_text(existing, encoding="utf-8")

    _create(redirect.parent / "env", "--venv-redirect")

    assert redirect.read_text(encoding="utf-8") == existing


_NON_FILE_KINDS: Final[list[pytest.ParameterSet]] = [
    pytest.param("directory", id="directory"),
    pytest.param("fifo", id="fifo"),
]


def _make_non_file(path: Path, kind: str) -> None:
    if kind == "directory":
        path.mkdir()
    elif hasattr(os, "mkfifo"):
        os.mkfifo(path)
    else:
        pytest.skip("requires FIFOs")


def _write_other_tool_cfg(path: Path) -> None:
    path.write_text("home = /usr/bin\nuv = 0.12.5\n", encoding="utf-8")


@pytest.mark.parametrize(
    "make_cfg",
    [
        pytest.param(_write_other_tool_cfg, id="other-tool"),
        pytest.param(partial(_make_non_file, kind="directory"), id="directory"),
        pytest.param(partial(_make_non_file, kind="fifo"), id="fifo"),
    ],
)
def test_venv_redirect_forced_keeps_other_environment(redirect: Path, make_cfg: Callable[[Path], None]) -> None:
    other = redirect.parent / "other"
    other.mkdir()
    make_cfg(other / "pyvenv.cfg")
    redirect.write_text("other\n", encoding="utf-8")

    _create(redirect.parent / "env", "--venv-redirect")

    assert redirect.read_text(encoding="utf-8") == "other\n"


@pytest.mark.parametrize("kind", _NON_FILE_KINDS)
def test_venv_redirect_forced_keeps_non_file(redirect: Path, kind: str) -> None:
    _make_non_file(redirect, kind)
    file_type: Final[int] = S_IFMT(redirect.stat().st_mode)

    _create(redirect.parent / "env", "--venv-redirect")

    assert (redirect.parent / "env" / "pyvenv.cfg").is_file()
    assert S_IFMT(redirect.stat().st_mode) == file_type


def test_venv_redirect_forced_keeps_undecodable(redirect: Path) -> None:
    redirect.write_bytes(b"\xff\xfeenv\n")

    _create(redirect.parent / "env", "--venv-redirect")

    assert redirect.read_bytes() == b"\xff\xfeenv\n"


def test_venv_redirect_forced_keeps_venv_folder(redirect: Path, caplog: pytest.LogCaptureFixture) -> None:
    _create(redirect)

    with caplog.at_level(logging.DEBUG):
        _create(redirect.parent / "env", "--venv-redirect")

    assert f"{redirect} keeps being the default environment" in caplog.text


def test_venv_redirect_replaces_read_only_redirect(redirect: Path) -> None:
    _create(redirect.parent / "old", "--venv-redirect")
    redirect.write_text("old\n", encoding="utf-8")
    redirect.chmod(S_IREAD)
    try:
        _create(redirect.parent / "env", "--venv-redirect")
    finally:
        redirect.chmod(S_IREAD | S_IWRITE)

    assert redirect.read_text(encoding="utf-8") == "env\n"


@pytest.mark.parametrize("kind", _NON_FILE_KINDS)
def test_clear_recovers_non_file_config(tmp_path: Path, kind: str) -> None:
    _make_non_file(tmp_path / "pyvenv.cfg", kind)

    _create(tmp_path, "--clear")

    assert (tmp_path / "pyvenv.cfg").is_file()
