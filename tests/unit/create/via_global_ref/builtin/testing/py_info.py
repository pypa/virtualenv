from __future__ import annotations

from pathlib import Path

from python_discovery import PythonInfo


def read_fixture(fixture_name):
    return PythonInfo.from_json(fixture_file(fixture_name).read_text(encoding="utf-8"))


def fixture_file(fixture_name):
    file_mask = f"*{fixture_name}.json"
    files = Path(__file__).parent.parent.rglob(file_mask)
    try:
        return next(files)
    except StopIteration as exc:
        # Fixture file was not found in the testing root and its subdirs.
        raise FileNotFoundError(file_mask) from exc
