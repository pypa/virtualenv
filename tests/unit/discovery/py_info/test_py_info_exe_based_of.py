from __future__ import annotations

import logging
import os
from pathlib import Path

import pytest

from virtualenv.discovery.py_info import EXTENSIONS, PythonInfo
from virtualenv.info import IS_WIN, fs_is_case_sensitive, fs_supports_symlink

CURRENT = PythonInfo.current()


def test_discover_empty_folder(tmp_path, session_app_data):
    with pytest.raises(RuntimeError):
        CURRENT.discover_exe(session_app_data, prefix=str(tmp_path))


BASE = (CURRENT.install_path("scripts"), ".")


@pytest.mark.skipif(not fs_supports_symlink(), reason="symlink is not supported")
@pytest.mark.parametrize("suffix", sorted({".exe", ".cmd", ""} & set(EXTENSIONS) if IS_WIN else [""]))
@pytest.mark.parametrize("into", BASE)
@pytest.mark.parametrize("arch", [CURRENT.architecture, ""])
@pytest.mark.parametrize("version", [".".join(str(i) for i in CURRENT.version_info[0:i]) for i in range(3, 0, -1)])
@pytest.mark.parametrize("impl", [CURRENT.implementation, "python"])
def test_discover_ok(tmp_path, suffix, impl, version, arch, into, caplog, session_app_data):  # noqa: PLR0913
    caplog.set_level(logging.DEBUG)
    folder = tmp_path / into
    folder.mkdir(parents=True, exist_ok=True)
    name = f"{impl}{version}"
    if arch:
        name += f"-{arch}"
    name += suffix
    dest = folder / name
    os.symlink(CURRENT.executable, str(dest))
    pyvenv = Path(CURRENT.executable).parents[1] / "pyvenv.cfg"
    if pyvenv.exists():
        (folder / pyvenv.name).write_text(pyvenv.read_text(encoding="utf-8"), encoding="utf-8")
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
    CURRENT._cache_exe_discovery.clear()  # noqa: SLF001
    with pytest.raises(RuntimeError):
        CURRENT.discover_exe(session_app_data, inside_folder)
