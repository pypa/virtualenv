from __future__ import annotations

import os
import re
import runpy
import shutil
import sys
from importlib.metadata import distribution
from pathlib import Path
from subprocess import check_output
from typing import Final, NoReturn

import pytest

import virtualenv
from virtualenv.__main__ import run_with_catch
from virtualenv.util.error import ProcessCallFailedError


@pytest.mark.parametrize("implicit", [pytest.param(True, id="working-directory"), pytest.param(False, id="other-path")])
def test_module_entry_removes_implicit_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, implicit: bool
) -> None:
    monkeypatch.chdir(tmp_path)
    original: Final = sys.path.copy()
    monkeypatch.setattr(sys, "path", [str(tmp_path if implicit else tmp_path / "other"), *original])
    monkeypatch.setattr(sys, "argv", ["virtualenv", "--version"])
    with pytest.raises(SystemExit) as context:
        runpy.run_module("virtualenv", run_name="__main__")
    assert (context.value.code, sys.path) == (0, original if implicit else [str(tmp_path / "other"), *original])


@pytest.mark.skipif(os.name == "nt", reason="Windows keeps the working directory open")
def test_module_entry_without_working_directory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    directory: Final = tmp_path / "removed"
    directory.mkdir()
    monkeypatch.chdir(directory)
    directory.rmdir()
    monkeypatch.setattr(sys, "argv", ["virtualenv", "--version"])
    with pytest.raises(SystemExit) as context:
        runpy.run_module("virtualenv", run_name="__main__")
    assert context.value.code == 0


@pytest.fixture
def raise_on_session_done(mocker):
    def _func(exception) -> None:
        from virtualenv.run import session_via_cli  # ruff:ignore[import-outside-top-level]

        prev_session = session_via_cli

        def _session_via_cli(args, options=None, setup_logging=True, env=None) -> NoReturn:
            prev_session(args, options, setup_logging, env)
            raise exception

        mocker.patch("virtualenv.run.session_via_cli", side_effect=_session_via_cli)

    return _func


def test_fail_no_traceback(raise_on_session_done, tmp_path, capsys) -> None:
    raise_on_session_done(ProcessCallFailedError(code=2, out="out\n", err="err\n", cmd=["something"]))
    with pytest.raises(SystemExit) as context:
        run_with_catch([str(tmp_path)])
    assert context.value.code == 2
    out, err = capsys.readouterr()
    assert out == f"subprocess call failed for [{'something'!r}] with code 2\nout\nSystemExit: 2\n"
    assert err == "err\n"


def test_discovery_fails_no_discovery_plugin(mocker, tmp_path, capsys) -> None:
    mocker.patch("virtualenv.run.plugin.discovery.Discovery.entry_points_for", return_value={})
    with pytest.raises(SystemExit) as context:
        run_with_catch([str(tmp_path)])
    assert context.value.code == 1
    out, err = capsys.readouterr()
    assert "RuntimeError: No discovery plugin found. Try reinstalling virtualenv to fix this issue." in out
    assert not err


def test_fail_with_traceback(raise_on_session_done, tmp_path, capsys) -> None:
    raise_on_session_done(TypeError("something bad"))

    with pytest.raises(TypeError, match="something bad"):
        run_with_catch([str(tmp_path), "--with-traceback"])
    out, err = capsys.readouterr()
    assert not out
    assert not err


@pytest.mark.usefixtures("session_app_data")
def test_session_report_full(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    run_with_catch([str(tmp_path), "--setuptools", "bundle"])
    out, err = capsys.readouterr()
    assert not err
    lines = out.splitlines()
    regexes = [
        r"created virtual environment .* in \d+ms",
        r"  creator .*",
        r"  seeder .*",
        r"    added seed packages: .*pip==.*, setuptools==.*",
        r"  activators .*",
    ]
    _match_regexes(lines, regexes)


def _match_regexes(lines, regexes) -> None:
    for line, regex in zip(lines, regexes):
        comp_regex = re.compile(rf"^{regex}$")
        assert comp_regex.match(line), line


@pytest.mark.usefixtures("session_app_data")
def test_session_report_minimal(tmp_path, capsys) -> None:
    run_with_catch([str(tmp_path), "--activators", "", "--without-pip"])
    out, err = capsys.readouterr()
    assert not err
    lines = out.splitlines()
    regexes = [
        r"created virtual environment .* in \d+ms",
        r"  creator .*",
    ]
    _match_regexes(lines, regexes)


@pytest.mark.usefixtures("session_app_data")
def test_session_report_subprocess(tmp_path) -> None:
    # when called via a subprocess the logging framework should flush and POSIX line normalization happen
    out = check_output(
        [sys.executable, "-m", "virtualenv", str(tmp_path), "--activators", "powershell", "--without-pip"],
        text=True,
        encoding="utf-8",
    )
    lines = out.split("\n")
    regexes = [
        r"created virtual environment .* in \d+ms",
        r"  creator .*",
        r"  activators .*",
    ]
    _match_regexes(lines, regexes)


def test_module_entry_from_target_install(tmp_path: Path) -> None:
    shutil.copytree(Path(virtualenv.__file__).parent, tmp_path / "virtualenv")
    metadata = distribution("virtualenv")
    for file in metadata.files or ():
        if file.name == "METADATA":
            shutil.copytree(Path(metadata.locate_file(file)).parent, tmp_path / file.parent.name)
            break
    check_output(
        [sys.executable, "-m", "virtualenv", str(tmp_path / "env"), "--no-seed", "--activators="],
        cwd=tmp_path,
        text=True,
        encoding="utf-8",
    )
    assert (tmp_path / "env" / "pyvenv.cfg").is_file()
