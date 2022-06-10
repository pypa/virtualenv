from virtualenv.discovery.py_info import PythonInfo
from virtualenv.info import PY2
from virtualenv.util.path import Path


def fixture_file(fixture_name):
    file_mask = "*{}.json".format(fixture_name)
    files = Path(__file__).parent.parent.rglob(file_mask)
    try:
        return next(files)
    except StopIteration:
        # Fixture file was not found in the testing root and its subdirs.
        error = NameError if PY2 else FileNotFoundError
        raise error(file_mask)


def read_fixture(fixture_name):
    fixture_json = fixture_file(fixture_name).read_text()
    return PythonInfo._from_json(fixture_json)
