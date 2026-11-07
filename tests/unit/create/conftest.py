from __future__ import annotations

import sys
from subprocess import Popen
from typing import TYPE_CHECKING, Final

import pytest
from python_discovery import PythonInfo

if TYPE_CHECKING:
    from pathlib import Path

_CURRENT: Final[PythonInfo] = PythonInfo.current_system()


def root(tmp_path_factory, session_app_data):  # ruff:ignore[unused-function-argument]
    return _CURRENT.system_executable


def venv(tmp_path_factory, session_app_data):
    if _CURRENT.is_venv:
        return sys.executable
    root_python = root(tmp_path_factory, session_app_data)
    dest = tmp_path_factory.mktemp("venv")
    Popen([str(root_python), "-m", "venv", "--without-pip", str(dest)]).communicate()
    # sadly creating a virtual environment does not tell us where the executable lives in general case
    # so discover using some heuristic
    return _CURRENT.discover_exe(prefix=str(dest)).original_executable


_PYTHON: Final[dict[str, Path]] = {
    "root": root,
    "venv": venv,
}


@pytest.fixture(params=list(_PYTHON.values()), ids=list(_PYTHON.keys()), scope="session")
def python(request, tmp_path_factory, session_app_data):
    result = request.param(tmp_path_factory, session_app_data)
    if isinstance(result, Exception):
        pytest.skip(f"could not resolve interpreter based on {request.param.__name__} because {result}")
    if result is None:
        pytest.skip(f"requires interpreter with {request.param.__name__}")
    return result
