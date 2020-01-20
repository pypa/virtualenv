from __future__ import absolute_import, unicode_literals

import logging
import os

import pytest

from virtualenv.discovery.py_info import CURRENT, EXTENSIONS
from virtualenv.info import fs_is_case_sensitive, fs_supports_symlink


def test_discover_empty_folder(tmp_path, monkeypatch):
    with pytest.raises(RuntimeError):
        CURRENT.find_exe_based_of(inside_folder=str(tmp_path))


@pytest.mark.skipif(not fs_supports_symlink(), reason="symlink is not supported")
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
    if not fs_is_case_sensitive():
        found = found.lower()
        dest_str = dest_str.lower()
    assert found == dest_str
    assert len(caplog.messages) >= 1, caplog.text
    assert "get interpreter info via cmd: " in caplog.text

    dest.rename(dest.parent / (dest.name + "-1"))
    with pytest.raises(RuntimeError):
        CURRENT.find_exe_based_of(inside_folder)
