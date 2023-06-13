from __future__ import annotations

from pathlib import Path

from virtualenv.discovery.py_info import PythonInfo


def fixture_file(fixture_name):
    file_mask = f"*{fixture_name}.json"
    files = Path(__file__).parent.parent.rglob(file_mask)
    try:
        return next(files)
    except StopIteration as exc:
        # Fixture file was not found in the testing root and its subdirs.
        error = FileNotFoundError
        raise error(file_mask) from exc


def read_fixture(fixture_name):
    fixture_json = fixture_file(fixture_name).read_text(encoding="utf-8")
    return PythonInfo._from_json(fixture_json)  # noqa: SLF001
