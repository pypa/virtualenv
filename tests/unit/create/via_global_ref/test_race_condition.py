from __future__ import annotations

import sys
from pathlib import Path


def test_virtualenv_py_race_condition_find_spec(tmp_path) -> None:
    # Test that _Finder.find_spec handles NameError gracefully when _DISTUTILS_PATCH is not defined.
    # Create a temporary file with partial _virtualenv.py content (simulating race condition)
    venv_file = tmp_path / "_virtualenv_test.py"

    # Write a partial version of _virtualenv.py that has _Finder but not _DISTUTILS_PATCH
    # This simulates the state during a race condition where the file is being rewritten
    partial_content = (Path(__file__).parent / "_test_race_condition_helper.py").read_text(encoding="utf-8")

    venv_file.write_text(partial_content, encoding="utf-8")

    sys.path.insert(0, str(tmp_path))
    try:
        _test_finder_behavior()
    finally:
        sys.path.remove(str(tmp_path))
        sys.modules.pop("_virtualenv_test", None)


def _test_finder_behavior() -> None:
    # the import checks the fixture module is on sys.path, the name is not used
    import _virtualenv_test  # ruff:ignore[import-outside-top-level, import-private-name]  # simplint: ignore[private-import-path]  # race fixture  # fmt: skip

    finder = _virtualenv_test._FINDER  # ruff:ignore[private-member-access]  # the helper is exec'd, its finder is private

    result = finder.find_spec("distutils.dist", None)
    assert result is None, "find_spec should return None when _DISTUTILS_PATCH is not defined"

    class MockModule:
        __name__ = "distutils.dist"

    def mock_old_exec(_x) -> None:
        pass

    finder.exec_module(mock_old_exec, MockModule())
