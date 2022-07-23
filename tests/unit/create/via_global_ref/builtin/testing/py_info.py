from pathlib import Path

from virtualenv.discovery.py_info import PythonInfo


def fixture_file(fixture_name):
    file_mask = f"*{fixture_name}.json"
    files = Path(__file__).parent.parent.rglob(file_mask)
    try:
        return next(files)
    except StopIteration:
        # Fixture file was not found in the testing root and its subdirs.
        error = FileNotFoundError
        raise error(file_mask)


def read_fixture(fixture_name):
    fixture_json = fixture_file(fixture_name).read_text()
    return PythonInfo._from_json(fixture_json)
