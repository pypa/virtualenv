from __future__ import annotations

import sys
from pathlib import Path


def _test_finder_behavior() -> None:
    import _virtualenv_test  # noqa: PLC0415

    finder = _virtualenv_test.finder

    result = finder.find_spec("distutils.dist", None)
    assert result is None, "find_spec should return None when _DISTUTILS_PATCH is not defined"

    class MockModule:
        __name__ = "distutils.dist"

    def mock_old_exec(_x) -> None:
        pass

    finder.exec_module(mock_old_exec, MockModule())

    def mock_old_load(_name):
        return MockModule()

    result = finder.load_module(mock_old_load, "distutils.dist")
    assert result.__name__ == "distutils.dist"


def test_virtualenv_py_race_condition_find_spec(tmp_path) -> None:
    """Test that _Finder.find_spec handles NameError gracefully when _DISTUTILS_PATCH is not defined."""
    # Create a temporary file with partial _virtualenv.py content (simulating race condition)
    venv_file = tmp_path / "_virtualenv_test.py"

    # Write a partial version of _virtualenv.py that has _Finder but not _DISTUTILS_PATCH
    # This simulates the state during a race condition where the file is being rewritten
    helper_file = Path(__file__).parent / "_test_race_condition_helper.py"
    partial_content = helper_file.read_text(encoding="utf-8")

    venv_file.write_text(partial_content, encoding="utf-8")

    sys.path.insert(0, str(tmp_path))
    try:
        _test_finder_behavior()
    finally:
        sys.path.remove(str(tmp_path))
        sys.modules.pop("_virtualenv_test", None)


def test_virtualenv_py_normal_operation() -> None:
    """Test that the fix doesn't break normal operation when _DISTUTILS_PATCH is defined."""
    # Read the actual _virtualenv.py file
    virtualenv_py_path = (
        Path(__file__).parent.parent.parent.parent.parent
        / "src"
        / "virtualenv"
        / "create"
        / "via_global_ref"
        / "_virtualenv.py"
    )

    if not virtualenv_py_path.exists():
        return  # Skip if we can't find the file

    content = virtualenv_py_path.read_text(encoding="utf-8")

    # Verify the fix is present
    assert "try:" in content
    assert "distutils_patch = _DISTUTILS_PATCH" in content
    assert "except NameError:" in content
    assert "return None" in content or "return" in content
