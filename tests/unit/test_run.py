from __future__ import absolute_import, unicode_literals

import pytest

from virtualenv import __version__
from virtualenv.run import run_via_cli


def test_help(capsys):
    with pytest.raises(SystemExit) as context:
        run_via_cli(args=["-h"])
    assert context.value.code == 0

    out, err = capsys.readouterr()
    assert not err
    assert out


def test_version(capsys):
    with pytest.raises(SystemExit) as context:
        run_via_cli(args=["--version"])
    assert context.value.code == 0

    out, err = capsys.readouterr()
    assert not err

    assert __version__ in out
    import virtualenv

    assert virtualenv.__file__ in out
