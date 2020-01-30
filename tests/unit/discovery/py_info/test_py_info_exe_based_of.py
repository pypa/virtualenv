from __future__ import absolute_import, unicode_literals

import logging
import os

import pytest

from virtualenv.discovery.py_info import EXTENSIONS, PythonInfo
from virtualenv.info import IS_WIN, fs_is_case_sensitive, fs_supports_symlink
from virtualenv.util.path import Path

CURRENT = PythonInfo.current()


def test_discover_empty_folder(tmp_path, monkeypatch):
    with pytest.raises(RuntimeError):
        CURRENT.discover_exe(prefix=str(tmp_path))


BASE = {str(Path(CURRENT.executable).parent.relative_to(Path(CURRENT.prefix))), "."}


@pytest.mark.skipif(not fs_supports_symlink(), reason="symlink is not supported")
@pytest.mark.parametrize("suffix", {".exe", ".cmd", ""} & set(EXTENSIONS) if IS_WIN else [""])
@pytest.mark.parametrize("into", BASE)
@pytest.mark.parametrize("arch", [CURRENT.architecture, ""])
@pytest.mark.parametrize("version", [".".join(str(i) for i in CURRENT.version_info[0:i]) for i in range(3, 0, -1)])
@pytest.mark.parametrize("impl", [CURRENT.implementation, "python"])
def test_discover_ok(tmp_path, monkeypatch, suffix, impl, version, arch, into, caplog):
    caplog.set_level(logging.DEBUG)
    folder = tmp_path / into
    folder.mkdir(parents=True, exist_ok=True)
    dest = folder / "{}{}".format(impl, version, arch, suffix)
    os.symlink(CURRENT.executable, str(dest))
    inside_folder = str(tmp_path)
    base = CURRENT.discover_exe(inside_folder)
    found = base.executable
    dest_str = str(dest)
    if not fs_is_case_sensitive():
        found = found.lower()
        dest_str = dest_str.lower()
    assert found == dest_str
    assert len(caplog.messages) >= 1, caplog.text
    assert "get interpreter info via cmd: " in caplog.text

    dest.rename(dest.parent / (dest.name + "-1"))
    CURRENT._cache_exe_discovery.clear()
    with pytest.raises(RuntimeError):
        CURRENT.discover_exe(inside_folder)
