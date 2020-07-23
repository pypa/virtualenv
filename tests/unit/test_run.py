from __future__ import absolute_import, unicode_literals

import logging

import pytest
import six

from virtualenv import __version__
from virtualenv.run import cli_run, session_via_cli


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


@pytest.mark.parametrize("on", [True, False])
def test_logging_setup(caplog, on):
    caplog.set_level(logging.DEBUG)
    session_via_cli(["env"], setup_logging=on)
    # DEBUG only level output is generated during this phase, default output is WARN, so if on no records should be
    if on:
        assert not caplog.records
    else:
        assert caplog.records
