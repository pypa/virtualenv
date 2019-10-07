from __future__ import absolute_import, unicode_literals

import os
import sys

import pytest

from virtualenv.config.cli import parse_core_cli
from virtualenv.interpreters.create.impl.cpython.cpython3 import CPython3Posix
from virtualenv.interpreters.discovery import CURRENT


def parse_cli(args):
    return parse_core_cli(args, CPython3Posix, CURRENT)


def test_default(tmp_path):
    result = parse_cli(args=[str(tmp_path)])

    assert result.clear is False
    assert result.dest_dir == str(tmp_path)

    assert result.quiet == 0
    assert result.verbose == 3

    assert result.python == sys.executable
    assert result.prompt is None

    assert result.download is False
    assert result.without_pip is False
    assert result.pip is None
    assert result.setuptools is None

    assert result.no_venv is False
    symlink_default = False if sys.platform == "win32" else True
    assert result.symlinks is symlink_default
    assert result.system_site is False

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


def test_help(capsys):
    with pytest.raises(SystemExit) as context:
        parse_cli(args=["-h"])
    assert context.value.code == 0

    out, err = capsys.readouterr()
    assert not err
    assert out


def test_no_arg_fails(capsys):
    with pytest.raises(SystemExit) as context:
        parse_cli(args=[])
    assert context.value.code == 2
    out, err = capsys.readouterr()
    assert not out
    assert "virtualenv: error: the following arguments are required: dest_dir"


def test_os_path_sep_not_allowed(tmp_path, capsys):
    target = str(tmp_path / "a{}b".format(os.pathsep))
    err = _non_success_exit_code(capsys, target)
    msg = "destination {!r} must not contain the path separator ({}) as this would break the activation scripts".format(
        target, os.pathsep
    )
    assert msg in err, err


def _non_success_exit_code(capsys, target):
    with pytest.raises(SystemExit) as context:
        parse_cli(args=[target])
    assert context.value.code != 0
    out, err = capsys.readouterr()
    assert not out, out
    return err


def test_destination_exists_file(tmp_path, capsys):
    target = tmp_path / "out"
    target.write_text("")
    err = _non_success_exit_code(capsys, str(target))
    msg = "the destination {} already exists and is a file".format(str(target))
    assert msg in err, err


@pytest.mark.skipif(sys.platform == "win32", reason="no chmod on Windows")
def test_destination_not_write_able(tmp_path, capsys):
    target = tmp_path
    prev_mod = target.stat().st_mode
    target.chmod(0o444)
    try:
        err = _non_success_exit_code(capsys, str(target))
        msg = "the destination . is not write-able at {}".format(str(target))
        assert msg in err, err
    finally:
        target.chmod(prev_mod)
