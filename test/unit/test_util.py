from __future__ import absolute_import, unicode_literals

import logging
import os

import pytest

from virtualenv.util import run_cmd, symlink_or_copy


@pytest.mark.skipif(not hasattr(os, "symlink"), reason="requires symlink support")
def test_fallback_to_copy_if_symlink_fails(caplog, tmp_path, mocker):
    mocker.patch("os.symlink", side_effect=OSError())
    dst, src = _try_symlink(caplog, tmp_path, level=logging.WARNING)
    msg = "symlink failed {!r}, for {} to {}, will try copy".format(OSError(), src, dst)
    assert len(caplog.messages) == 1, caplog.text
    message = caplog.messages[0]
    assert msg == message


def _try_symlink(caplog, tmp_path, level):
    caplog.set_level(level)
    src = tmp_path / "src"
    src.write_text("a")
    dst = tmp_path / "dst"
    symlink_or_copy(do_copy=False, src=src, dst=dst)
    assert dst.exists()
    assert not dst.is_symlink()
    assert dst.read_text() == "a"
    return dst, src


@pytest.mark.skipif(hasattr(os, "symlink"), reason="requires no symlink")
def test_os_no_symlink_use_copy(caplog, tmp_path):
    dst, src = _try_symlink(caplog, tmp_path, level=logging.DEBUG)
    assert caplog.messages == ["copy {} to {}".format(src, dst)]


def test_run_fail(tmp_path):
    code, out, err = run_cmd([str(tmp_path)])
    assert err
    assert not out
    assert code
