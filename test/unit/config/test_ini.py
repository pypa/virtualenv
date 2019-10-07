from __future__ import absolute_import, unicode_literals

import re
import sys
import textwrap

import pytest

from virtualenv.config.cli import parse_core_cli
from virtualenv.config.convert import _convert_to_boolean
from virtualenv.interpreters.create.impl.cpython.cpython3 import CPython3Posix
from virtualenv.interpreters.discovery import CURRENT


def parse_cli(args):
    return parse_core_cli(args, CPython3Posix, CURRENT)


@pytest.fixture(scope="session")
def conf(tmp_path_factory):
    base = tmp_path_factory.mktemp("conf")
    conf = base / "conf.ini"
    content = textwrap.dedent(
        """
    [virtualenv]
    clear = true
    dest_dir = {0}
    quiet = 2
    verbose = 1
    python = python2.7
    prompt = what
    download = true
    no_pip = true
    no_setuptools = true
    no_wheel = true
    without_pip = True
    pip = 1.0.0
    setuptools = 2.0.0
    no_venv = true
    symlinks= false
    system_site = true
    """
    ).strip()
    conf.write_text(content.format(base, conf))
    yield conf


def test_ini_file(tmp_path, monkeypatch, conf, capsys, caplog):
    monkeypatch.setenv(str("VIRTUALENV_CONFIG_FILE"), str(conf))

    explicit_dest = tmp_path / "dest"
    result = parse_cli([str(explicit_dest)])

    out, err = capsys.readouterr()
    assert not out
    assert not err
    assert not caplog.records, caplog.text

    assert result.clear is True
    assert result.dest_dir == str(explicit_dest)

    assert result.quiet == 2
    assert result.verbose == 1

    assert result.python == "python2.7"
    assert result.prompt == "what"

    assert result.download is True
    assert result.without_pip is True
    assert result.pip == "1.0.0"
    assert result.setuptools == "2.0.0"

    assert result.no_venv is True
    assert result.symlinks is False
    assert result.system_site is True

    keys = set(vars(result))
    assert keys == {
        "clear",
        "dest_dir",
        "download",
        "no_venv",
        "pip",
        "prompt",
        "python",
        "quiet",
        "setuptools",
        "symlinks",
        "system_site",
        "verbose",
        "without_pip",
    }


def test_help_conf_ini(capsys, monkeypatch, conf):
    out = _invoke_help_with_conf_file_as_env_var(capsys, monkeypatch, conf)
    from pathlib2 import Path

    print(Path(conf).read_text())
    print(out)
    epilog = "config file {} active (changed via env var VIRTUALENV_CONFIG_FILE)".format(conf)
    assert out.rstrip().endswith(epilog)

    elements = [
        i.groups()
        for i in [
            re.match(r"([a-zA-Z-, ]+) [ ]+.*\(default: (.*) -> from file\)", "-{}".format(s).replace("\n", ""))
            for s in out.split("  -")[1:]
        ]
        if i
    ]
    assert len(elements) >= 11


def test_conf_ini_dir(capsys, monkeypatch, tmp_path, caplog):
    out = _invoke_help_with_conf_file_as_env_var(capsys, monkeypatch, tmp_path)

    err = "config file {} failed to parse (changed via env var VIRTUALENV_CONFIG_FILE)".format(tmp_path)
    assert out.rstrip().endswith(err)

    msg = caplog.records[0].message
    assert "failed to read config file {} because".format(tmp_path) in msg
    cannot_read_msg = "Permission denied" if sys.platform == "win32" else "Is a directory"
    assert cannot_read_msg in msg


def test_bad_ini_format(tmp_path, monkeypatch, capsys, caplog):
    conf = tmp_path / "conf.ini"
    conf.write_text("x s {}")
    out = _invoke_help_with_conf_file_as_env_var(capsys, monkeypatch, conf)
    assert out
    msg = "failed to read config file {} because File contains no section headers.".format(conf)
    assert msg in caplog.records[0].message


def _invoke_help_with_conf_file_as_env_var(capsys, monkeypatch, conf):
    monkeypatch.setenv(str("VIRTUALENV_CONFIG_FILE"), str(conf))
    with pytest.raises(SystemExit) as context:
        parse_cli(args=["-h"])
    assert context.value.code == 0
    out, err = capsys.readouterr()
    assert not err
    return out


def test_bad_ini_conversion(tmp_path, monkeypatch, capsys, caplog):
    conf = tmp_path / "conf.ini"
    conf.write_text(
        textwrap.dedent(
            """
    [virtualenv]
    quiet = info
    verbose = critical
    download = whatever
    prompt =
    """
        )
    )
    monkeypatch.setenv(str("VIRTUALENV_CONFIG_FILE"), str(conf))
    result = parse_cli([str(tmp_path)])
    assert result.verbose == 3
    assert result.quiet == 0
    assert result.prompt is None
    assert result.download is False

    def _exc(of):
        try:
            int(of)
        except ValueError as exception:
            return exception

    records = [r.message for r in caplog.records]
    expected = [
        "file failed to convert {!r} as {!r} because {!r}".format("critical", int, _exc("critical")),
        "file failed to convert {!r} as {!r} because {!r}".format("info", int, _exc("info")),
        "file failed to convert {!r} as {!r} because {!r}".format(
            "whatever", _convert_to_boolean, ValueError("Not a boolean: whatever")
        ),
    ]
    assert records == expected, caplog.text
