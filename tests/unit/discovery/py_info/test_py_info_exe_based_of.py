from __future__ import absolute_import, unicode_literals

import logging
import os

import pytest

from virtualenv.discovery.py_info import EXTENSIONS, PythonInfo
from virtualenv.info import IS_WIN, fs_is_case_sensitive, fs_supports_symlink
from virtualenv.util.path import Path

CURRENT = PythonInfo.current()


def test_discover_empty_folder(tmp_path, monkeypatch, session_app_data):
    with pytest.raises(RuntimeError):
        CURRENT.discover_exe(session_app_data, prefix=str(tmp_path))


BASE = (CURRENT.distutils_install["scripts"], ".")


@pytest.mark.skipif(not fs_supports_symlink(), reason="symlink is not supported")
@pytest.mark.parametrize("suffix", sorted({".exe", ".cmd", ""} & set(EXTENSIONS) if IS_WIN else [""]))
@pytest.mark.parametrize("into", BASE)
@pytest.mark.parametrize("arch", [CURRENT.architecture, ""])
@pytest.mark.parametrize("version", [".".join(str(i) for i in CURRENT.version_info[0:i]) for i in range(3, 0, -1)])
@pytest.mark.parametrize("impl", [CURRENT.implementation, "python"])
def test_discover_ok(tmp_path, monkeypatch, suffix, impl, version, arch, into, caplog, session_app_data):
    caplog.set_level(logging.DEBUG)
    folder = tmp_path / into
    folder.mkdir(parents=True, exist_ok=True)
    name = "{}{}".format(impl, version)
    if arch:
        name += "-{}".format(arch)
    name += suffix
    dest = folder / name
    os.symlink(CURRENT.executable, str(dest))
    pyvenv = Path(CURRENT.executable).parents[1] / "pyvenv.cfg"
    if pyvenv.exists():
        (folder / pyvenv.name).write_text(pyvenv.read_text())
    inside_folder = str(tmp_path)
    base = CURRENT.discover_exe(session_app_data, inside_folder)
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
        CURRENT.discover_exe(session_app_data, inside_folder)
