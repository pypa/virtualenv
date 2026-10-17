from __future__ import annotations

import logging
import os
from stat import S_IREAD, S_IWRITE
from typing import TYPE_CHECKING, Final

import pytest

from virtualenv.run import cli_run

if TYPE_CHECKING:
    from pathlib import Path


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


def test_venv_redirect_forced_points_at_created(redirect: Path) -> None:
    _create(redirect.parent / "env", "--venv-redirect")

    assert redirect.read_text(encoding="utf-8") == "env\n"


@pytest.mark.parametrize(
    "name",
    [
        *(
            pytest.param(f"env{chr(code)}name", id=f"U+{code:04X}")
            for code in (10, 13, 11, 12, 28, 29, 30, 133, 8232, 8233)
        ),
        pytest.param(" env", id="leading-whitespace"),
        pytest.param(
            "env ",
            id="trailing-whitespace",
            marks=pytest.mark.skipif(os.name == "nt", reason="Windows strips trailing whitespace from names"),
        ),
    ],
)
@pytest.mark.parametrize("existing", [pytest.param(False, id="new"), pytest.param(True, id="existing")])
def test_venv_redirect_skips_unrepresentable_names(project_redirect: Path, name: str, existing: bool) -> None:
    if os.name == "nt" and any(ord(char) < 32 for char in name):
        pytest.skip("Windows rejects control characters in directory names")
    if existing:
        cli_run([str(project_redirect.parent / "old"), "--without-pip", "--activators", ""])
    cli_run([
        str(project_redirect.parent / name),
        "--without-pip",
        "--activators",
        "",
        "--venv-redirect",
    ])
    assert (project_redirect.read_text(encoding="utf-8") if project_redirect.exists() else None) == (
        "old\n" if existing else None
    )


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


_NON_FILE_KINDS: Final = [pytest.param("directory", id="directory"), pytest.param("fifo", id="fifo")]


@pytest.mark.parametrize("kind", [pytest.param("other_tool", id="other-tool"), *_NON_FILE_KINDS])
def test_venv_redirect_forced_keeps_other_environment(redirect: Path, kind: str) -> None:
    other = redirect.parent / "other"
    other.mkdir()
    if kind == "other_tool":
        (other / "pyvenv.cfg").write_text("home = /usr/bin\nuv = 0.12.5\n", encoding="utf-8")
    else:
        _make_non_file(other / "pyvenv.cfg", kind)
    redirect.write_text("other\n", encoding="utf-8")

    _create(redirect.parent / "env", "--venv-redirect")

    assert redirect.read_text(encoding="utf-8") == "other\n"


def test_venv_redirect_forced_keeps_undecodable(redirect: Path) -> None:
    redirect.write_bytes(b"\xff\xfeenv\n")

    _create(redirect.parent / "env", "--venv-redirect")

    assert redirect.read_bytes() == b"\xff\xfeenv\n"


def test_venv_redirect_forced_keeps_venv_folder(redirect: Path, caplog: pytest.LogCaptureFixture) -> None:
    _create(redirect)

    with caplog.at_level(logging.DEBUG):
        _create(redirect.parent / "env", "--venv-redirect")

    assert f"{redirect} keeps being the default environment" in caplog.text


def test_venv_redirect_forced_not_write_able(redirect: Path, caplog: pytest.LogCaptureFixture) -> None:
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        pytest.skip("root may write read-only files")
    _create(redirect.parent / "old", "--venv-redirect")
    redirect.write_text("old\n", encoding="utf-8")
    redirect.chmod(S_IREAD)
    try:
        with caplog.at_level(logging.WARNING):
            _create(redirect.parent / "env", "--venv-redirect")
    finally:
        redirect.chmod(S_IREAD | S_IWRITE)

    assert f"could not point {redirect.resolve()} at {(redirect.parent / 'env').resolve()}" in caplog.text


def _make_non_file(path: Path, kind: str) -> None:
    if kind == "directory":
        path.mkdir()
    elif hasattr(os, "mkfifo"):
        os.mkfifo(path)
    else:
        pytest.skip("requires FIFOs")


@pytest.mark.parametrize("kind", _NON_FILE_KINDS)
def test_clear_recovers_non_file_config(tmp_path: Path, kind: str) -> None:
    _make_non_file(tmp_path / "pyvenv.cfg", kind)

    _create(tmp_path, "--clear")

    assert (tmp_path / "pyvenv.cfg").is_file()
