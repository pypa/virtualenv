from __future__ import annotations

import sys
from pathlib import Path

import pytest
from testing import path
from testing.py_info import read_fixture

# Allows to import from `testing` into test submodules.
sys.path.append(str(Path(__file__).parent))


@pytest.fixture
def py_info(py_info_name):
    return read_fixture(py_info_name)


@pytest.fixture
def mock_files(mocker):
    return lambda paths, files: path.mock_files(mocker, paths, files)


@pytest.fixture
def mock_pypy_libs(mocker):
    return lambda pypy, libs: path.mock_pypy_libs(mocker, pypy, libs)
