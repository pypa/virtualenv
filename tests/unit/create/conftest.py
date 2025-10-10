"""
It's possible to use multiple types of host pythons to create virtual environments and all should work:

- host installation
- invoking from a venv (if Python 3.3+)
- invoking from an old style virtualenv (<17.0.0)
- invoking from our own venv
"""

from __future__ import annotations

import sys
from subprocess import Popen

import pytest

from virtualenv.discovery.py_info import PythonInfo

CURRENT = PythonInfo.current_system()


def root(tmp_path_factory, session_app_data):  # noqa: ARG001
    return CURRENT.system_executable


def venv(tmp_path_factory, session_app_data):
    if CURRENT.is_venv:
        return sys.executable
    root_python = root(tmp_path_factory, session_app_data)
    dest = tmp_path_factory.mktemp("venv")
    process = Popen([str(root_python), "-m", "venv", "--without-pip", str(dest)])
    process.communicate()
    # sadly creating a virtual environment does not tell us where the executable lives in general case
    # so discover using some heuristic
    return CURRENT.discover_exe(prefix=str(dest)).original_executable


PYTHON = {
    "root": root,
    "venv": venv,
}


@pytest.fixture(params=list(PYTHON.values()), ids=list(PYTHON.keys()), scope="session")
def python(request, tmp_path_factory, session_app_data):
    result = request.param(tmp_path_factory, session_app_data)
    if isinstance(result, Exception):
        pytest.skip(f"could not resolve interpreter based on {request.param.__name__} because {result}")
    if result is None:
        pytest.skip(f"requires interpreter with {request.param.__name__}")
    return result
