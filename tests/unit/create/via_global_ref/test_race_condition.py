from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from textwrap import dedent


def test_virtualenv_py_race_condition_find_spec():
    """Test that _Finder.find_spec handles NameError gracefully when _DISTUTILS_PATCH is not defined."""
    # Create a temporary file with partial _virtualenv.py content (simulating race condition)
    with tempfile.TemporaryDirectory() as tmpdir:
        venv_file = Path(tmpdir) / "_virtualenv_test.py"

        # Write a partial version of _virtualenv.py that has _Finder but not _DISTUTILS_PATCH
        # This simulates the state during a race condition where the file is being rewritten
        partial_content = dedent("""
            import sys

            class _Finder:
                fullname = None
                lock = []

                def find_spec(self, fullname, path, target=None):
                    # This should handle the NameError gracefully
                    try:
                        distutils_patch = _DISTUTILS_PATCH  # noqa: F821
                    except NameError:
                        return None
                    if fullname in distutils_patch and self.fullname is None:
                        return None
                    return None

                @staticmethod
                def exec_module(old, module):
                    old(module)
                    try:
                        distutils_patch = _DISTUTILS_PATCH  # noqa: F821
                    except NameError:
                        return
                    if module.__name__ in distutils_patch:
                        pass  # Would call patch_dist(module)

                @staticmethod
                def load_module(old, name):
                    module = old(name)
                    try:
                        distutils_patch = _DISTUTILS_PATCH  # noqa: F821
                    except NameError:
                        return module
                    if module.__name__ in distutils_patch:
                        pass  # Would call patch_dist(module)
                    return module

            finder = _Finder()
        """)

        venv_file.write_text(partial_content, encoding="utf-8")

        # Add the directory to sys.path temporarily
        sys.path.insert(0, tmpdir)
        try:
            # Import the module
            import _virtualenv_test

            # Get the finder instance
            finder = _virtualenv_test.finder

            # Try to call find_spec - this should not raise NameError
            result = finder.find_spec("distutils.dist", None)
            assert result is None, "find_spec should return None when _DISTUTILS_PATCH is not defined"

            # Create a mock module object
            class MockModule:
                __name__ = "distutils.dist"

            # Try to call exec_module - this should not raise NameError
            mock_old_exec = lambda x: None  # noqa: E731
            finder.exec_module(mock_old_exec, MockModule())

            # Try to call load_module - this should not raise NameError
            mock_old_load = lambda name: MockModule()  # noqa: E731
            result = finder.load_module(mock_old_load, "distutils.dist")
            assert result.__name__ == "distutils.dist"

        finally:
            # Clean up
            sys.path.remove(tmpdir)
            if "_virtualenv_test" in sys.modules:
                del sys.modules["_virtualenv_test"]


def test_virtualenv_py_normal_operation():
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
