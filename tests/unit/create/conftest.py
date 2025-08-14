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

from virtualenv.cache import FileCache
from virtualenv.discovery.py_info import PythonInfo


@pytest.fixture(scope="session")
def current_info(session_app_data):
    cache = FileCache(session_app_data.py_info, session_app_data.py_info_clear)
    return PythonInfo.current_system(session_app_data, cache)


def root(tmp_path_factory, session_app_data, current_info):  # noqa: ARG001
    return current_info.system_executable


def venv(tmp_path_factory, session_app_data, current_info):
    if current_info.is_venv:
        return sys.executable
    root_python = root(tmp_path_factory, session_app_data, current_info)
    dest = tmp_path_factory.mktemp("venv")
    process = Popen([str(root_python), "-m", "venv", "--without-pip", str(dest)])
    process.communicate()
    # sadly creating a virtual environment does not tell us where the executable lives in general case
    # so discover using some heuristic
    cache = FileCache(session_app_data.py_info, session_app_data.py_info_clear)
    return current_info.discover_exe(session_app_data, cache, prefix=str(dest)).original_executable


PYTHON = {
    "root": root,
    "venv": venv,
}


@pytest.fixture(params=list(PYTHON.values()), ids=list(PYTHON.keys()), scope="session")
def python(request, tmp_path_factory, session_app_data, current_info):
    result = request.param(tmp_path_factory, session_app_data, current_info)
    if isinstance(result, Exception):
        pytest.skip(f"could not resolve interpreter based on {request.param.__name__} because {result}")
    if result is None:
        pytest.skip(f"requires interpreter with {request.param.__name__}")
    return result
