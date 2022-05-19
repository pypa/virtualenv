import sys

import pytest
from testing import path_mock

from virtualenv.discovery.py_info import PythonInfo
from virtualenv.util.path import Path

DIR = Path(__file__).parent

# Allows to import `testing` in submodules.
sys.path.append(DIR)


def fixture_file(fixture_name):
    file_mask = "*{}.json".format(fixture_name)
    files = DIR.rglob(file_mask)
    try:
        return next(files)
    except StopIteration:
        # Fixture file was not found in the current dir and subdirs.
        raise FileNotFoundError(file_mask)


@pytest.fixture
def py_info(py_info_name):
    py_info_file = fixture_file(py_info_name)
    py_info_json = py_info_file.read_text()
    return PythonInfo._from_json(py_info_json)


@pytest.fixture
def mock_files(mocker, mock_paths):
    return lambda files: path_mock.files(mocker, mock_paths, files)


@pytest.fixture
def mock_pypy_libs(mocker):
    return lambda pypy, libs: path_mock.pypy_libs(mocker, pypy, libs)
