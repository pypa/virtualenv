from __future__ import annotations

import logging
import os
import sys
from argparse import Namespace
from pathlib import Path
from uuid import uuid4

import pytest

from virtualenv.discovery.builtin import Builtin, get_interpreter
from virtualenv.discovery.py_info import PythonInfo
from virtualenv.info import fs_supports_symlink


@pytest.mark.skipif(not fs_supports_symlink(), reason="symlink not supported")
@pytest.mark.parametrize("case", ["mixed", "lower", "upper"])
@pytest.mark.parametrize("specificity", ["more", "less", "none"])
def test_discovery_via_path(monkeypatch, case, specificity, tmp_path, caplog, session_app_data):  # noqa: PLR0913
    caplog.set_level(logging.DEBUG)
    current = PythonInfo.current_system(session_app_data)
    name = "somethingVeryCryptic"
    if case == "lower":
        name = name.lower()
    elif case == "upper":
        name = name.upper()
    if specificity == "more":
        # e.g. spec: python3, exe: /bin/python3.12
        core_ver = current.version_info.major
        exe_ver = ".".join(str(i) for i in current.version_info[0:2])
    elif specificity == "less":
        # e.g. spec: python3.12.1, exe: /bin/python3
        core_ver = ".".join(str(i) for i in current.version_info[0:3])
        exe_ver = current.version_info.major
    elif specificity == "none":
        # e.g. spec: python3.12.1, exe: /bin/python
        core_ver = ".".join(str(i) for i in current.version_info[0:3])
        exe_ver = ""
    core = "" if specificity == "none" else f"{name}{core_ver}"
    exe_name = f"{name}{exe_ver}{'.exe' if sys.platform == 'win32' else ''}"
    target = tmp_path / current.install_path("scripts")
    target.mkdir(parents=True)
    executable = target / exe_name
    os.symlink(sys.executable, str(executable))
    pyvenv_cfg = Path(sys.executable).parents[1] / "pyvenv.cfg"
    if pyvenv_cfg.exists():
        (target / pyvenv_cfg.name).write_bytes(pyvenv_cfg.read_bytes())
    new_path = os.pathsep.join([str(target), *os.environ.get("PATH", "").split(os.pathsep)])
    monkeypatch.setenv("PATH", new_path)
    interpreter = get_interpreter(core, [])

    assert interpreter is not None


def test_discovery_via_path_not_found(tmp_path, monkeypatch):
    monkeypatch.setenv("PATH", str(tmp_path))
    interpreter = get_interpreter(uuid4().hex, [])
    assert interpreter is None


def test_discovery_via_path_in_nonbrowseable_directory(tmp_path, monkeypatch):
    bad_perm = tmp_path / "bad_perm"
    bad_perm.mkdir(mode=0o000)
    monkeypatch.setenv("PATH", str(bad_perm / "bin"))
    interpreter = get_interpreter(uuid4().hex, [])
    assert interpreter is None


def test_relative_path(session_app_data, monkeypatch):
    sys_executable = Path(PythonInfo.current_system(app_data=session_app_data).system_executable)
    cwd = sys_executable.parents[1]
    monkeypatch.chdir(str(cwd))
    relative = str(sys_executable.relative_to(cwd))
    result = get_interpreter(relative, [], session_app_data)
    assert result is not None


def test_discovery_fallback_fail(session_app_data, caplog):
    caplog.set_level(logging.DEBUG)
    builtin = Builtin(
        Namespace(app_data=session_app_data, try_first_with=[], python=["magic-one", "magic-two"], env=os.environ),
    )

    result = builtin.run()
    assert result is None

    assert "accepted" not in caplog.text


def test_discovery_fallback_ok(session_app_data, caplog):
    caplog.set_level(logging.DEBUG)
    builtin = Builtin(
        Namespace(app_data=session_app_data, try_first_with=[], python=["magic-one", sys.executable], env=os.environ),
    )

    result = builtin.run()
    assert result is not None, caplog.text
    assert result.executable == sys.executable, caplog.text

    assert "accepted" in caplog.text
