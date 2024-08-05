from __future__ import annotations

import re
import sys
from subprocess import PIPE, Popen, check_output
from typing import TYPE_CHECKING

import pytest

from virtualenv.__main__ import run_with_catch
from virtualenv.util.error import ProcessCallFailedError

if TYPE_CHECKING:
    from pathlib import Path


def test_main():
    process = Popen(
        [sys.executable, "-m", "virtualenv", "--help"],
        universal_newlines=True,
        stdout=PIPE,
        encoding="utf-8",
    )
    out, _ = process.communicate()
    assert not process.returncode
    assert out


@pytest.fixture
def raise_on_session_done(mocker):
    def _func(exception):
        from virtualenv.run import session_via_cli  # noqa: PLC0415

        prev_session = session_via_cli

        def _session_via_cli(args, options=None, setup_logging=True, env=None):
            prev_session(args, options, setup_logging, env)
            raise exception

        mocker.patch("virtualenv.run.session_via_cli", side_effect=_session_via_cli)

    return _func


def test_fail_no_traceback(raise_on_session_done, tmp_path, capsys):
    raise_on_session_done(ProcessCallFailedError(code=2, out="out\n", err="err\n", cmd=["something"]))
    with pytest.raises(SystemExit) as context:
        run_with_catch([str(tmp_path)])
    assert context.value.code == 2
    out, err = capsys.readouterr()
    assert out == f"subprocess call failed for [{'something'!r}] with code 2\nout\nSystemExit: 2\n"
    assert err == "err\n"


def test_fail_with_traceback(raise_on_session_done, tmp_path, capsys):
    raise_on_session_done(TypeError("something bad"))

    with pytest.raises(TypeError, match="something bad"):
        run_with_catch([str(tmp_path), "--with-traceback"])
    out, err = capsys.readouterr()
    assert not out
    assert not err


@pytest.mark.usefixtures("session_app_data")
def test_session_report_full(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    run_with_catch([str(tmp_path), "--setuptools", "bundle", "--wheel", "bundle"])
    out, err = capsys.readouterr()
    assert not err
    lines = out.splitlines()
    regexes = [
        r"created virtual environment .* in \d+ms",
        r"  creator .*",
        r"  seeder .*",
        r"    added seed packages: .*pip==.*, setuptools==.*, wheel==.*",
        r"  activators .*",
    ]
    _match_regexes(lines, regexes)


def _match_regexes(lines, regexes):
    for line, regex in zip(lines, regexes):
        comp_regex = re.compile(rf"^{regex}$")
        assert comp_regex.match(line), line


@pytest.mark.usefixtures("session_app_data")
def test_session_report_minimal(tmp_path, capsys):
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
def test_session_report_subprocess(tmp_path):
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
