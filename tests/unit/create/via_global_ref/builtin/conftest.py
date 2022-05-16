import pytest

from virtualenv.discovery.py_info import PythonInfo
from virtualenv.util.path import Path


def fixture_file(fixture_name):
    file_mask = "*{}.json".format(fixture_name)
    current_dir = Path(__file__).parent
    files = current_dir.rglob(file_mask)
    try:
        return next(files)
    except StopIteration:
        # Fixture file was not found in the current dir and subdirs.
        raise FileNotFoundError(file_mask)


@pytest.fixture
def py_info(fixture_name):
    py_info_file = fixture_file(fixture_name)
    py_info_json = py_info_file.read_text()
    return PythonInfo._from_json(py_info_json)
