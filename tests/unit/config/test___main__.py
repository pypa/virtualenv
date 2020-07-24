from __future__ import absolute_import, unicode_literals

import os
import re
import sys

import pytest

from virtualenv.__main__ import run_with_catch
from virtualenv.util.error import ProcessCallFailed
from virtualenv.util.subprocess import Popen, subprocess


def test_main():
    process = Popen([sys.executable, "-m", "virtualenv", "--help"], universal_newlines=True, stdout=subprocess.PIPE)
    out, _ = process.communicate()
    assert not process.returncode
    assert out


@pytest.fixture()
def raise_on_session_done(mocker):
    def _func(exception):
        from virtualenv.run import session_via_cli

        prev_session = session_via_cli

        def _session_via_cli(args, options=None, setup_logging=True):
            prev_session(args, options, setup_logging)
            raise exception

        mocker.patch("virtualenv.run.session_via_cli", side_effect=_session_via_cli)

    return _func


def test_fail_no_traceback(raise_on_session_done, tmp_path, capsys):
    raise_on_session_done(ProcessCallFailed(code=2, out="out\n", err="err\n", cmd=["something"]))
    with pytest.raises(SystemExit) as context:
        run_with_catch([str(tmp_path)])
    assert context.value.code == 2
    out, err = capsys.readouterr()
    assert out == "subprocess call failed for [{}] with code 2\nout\nSystemExit: 2\n".format(repr("something"))
    assert err == "err\n"


def test_fail_with_traceback(raise_on_session_done, tmp_path, capsys):
    raise_on_session_done(TypeError("something bad"))

    with pytest.raises(TypeError, match="something bad"):
        run_with_catch([str(tmp_path), "--with-traceback"])
    out, err = capsys.readouterr()
    assert out == ""
    assert err == ""


def test_session_report_full(session_app_data, tmp_path, capsys):
    run_with_catch([str(tmp_path)])
    out, err = capsys.readouterr()
    assert err == ""
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
        comp_regex = re.compile(r"^{}$".format(regex))
        assert comp_regex.match(line), line


def test_session_report_minimal(session_app_data, tmp_path, capsys):
    run_with_catch([str(tmp_path), "--activators", "", "--without-pip"])
    out, err = capsys.readouterr()
    assert err == ""
    lines = out.splitlines()
    regexes = [
        r"created virtual environment .* in \d+ms",
        r"  creator .*",
    ]
    _match_regexes(lines, regexes)


def test_session_report_subprocess(session_app_data, tmp_path):
    # when called via a subprocess the logging framework should flush and POSIX line normalization happen
    out = subprocess.check_output(
        [sys.executable, "-m", "virtualenv", str(tmp_path), "--activators", "powershell", "--without-pip"],
    )
    lines = out.decode().split(os.linesep)
    regexes = [
        r"created virtual environment .* in \d+ms",
        r"  creator .*",
        r"  activators .*",
    ]
    _match_regexes(lines, regexes)
