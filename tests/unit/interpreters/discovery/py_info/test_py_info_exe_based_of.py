from __future__ import absolute_import, unicode_literals

import logging
import os
import sys

import pytest

from virtualenv.info import is_fs_case_sensitive
from virtualenv.interpreters.discovery.py_info import CURRENT, EXTENSIONS


def test_discover_empty_folder(tmp_path, monkeypatch):
    with pytest.raises(RuntimeError):
        CURRENT.find_exe_based_of(inside_folder=str(tmp_path))


@pytest.mark.skipif(sys.platform == "win32", reason="symlink is not guaranteed to work on windows")
@pytest.mark.parametrize("suffix", EXTENSIONS)
@pytest.mark.parametrize("arch", [CURRENT.architecture, ""])
@pytest.mark.parametrize("version", [".".join(str(i) for i in CURRENT.version_info[0:i]) for i in range(3, 0, -1)])
@pytest.mark.parametrize("impl", [CURRENT.implementation, "python"])
@pytest.mark.parametrize("into", [CURRENT.prefix[len(CURRENT.executable) :], ""])
def test_discover_ok(tmp_path, monkeypatch, suffix, impl, version, arch, into, caplog):
    caplog.set_level(logging.DEBUG)
    folder = tmp_path / into
    folder.mkdir(parents=True, exist_ok=True)
    dest = folder / "{}{}".format(impl, version, arch, suffix)
    os.symlink(CURRENT.executable, str(dest))
    inside_folder = str(tmp_path)
    found = CURRENT.find_exe_based_of(inside_folder)
    dest_str = str(dest)
    if not is_fs_case_sensitive():
        found = found.lower()
        dest_str = dest_str.lower()
    assert found == dest_str
    assert len(caplog.messages) >= 1, caplog.text
    assert "get interpreter info via cmd: " in caplog.text

    dest.rename(dest.parent / (dest.name + "-1"))
    with pytest.raises(RuntimeError):
        CURRENT.find_exe_based_of(inside_folder)
