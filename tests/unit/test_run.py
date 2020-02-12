from __future__ import absolute_import, unicode_literals

import pytest
import six

from virtualenv import __version__
from virtualenv.run import cli_run


def test_help(capsys):
    with pytest.raises(SystemExit) as context:
        cli_run(args=["-h", "-vvv"])
    assert context.value.code == 0

    out, err = capsys.readouterr()
    assert not err
    assert out


def test_version(capsys):
    with pytest.raises(SystemExit) as context:
        cli_run(args=["--version"])
    assert context.value.code == 0

    out, err = capsys.readouterr()
    extra = out if six.PY2 else err
    content = out if six.PY3 else err
    assert not extra

    assert __version__ in content
    import virtualenv

    assert virtualenv.__file__ in content
