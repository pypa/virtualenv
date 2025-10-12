from __future__ import annotations

import importlib.util
import sys
import tempfile
from pathlib import Path


def test_race_condition_simulation():
    """Test that simulates the race condition described in the issue.

    This test creates a temporary directory with _virtualenv.py and _virtualenv.pth,
    then simulates the scenario where:
    - One process imports and uses the _virtualenv module (simulating marimo)
    - Another process overwrites the _virtualenv.py file (simulating uv venv)

    The test verifies that no NameError is raised for _DISTUTILS_PATCH.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        venv_path = Path(tmpdir)

        # Create the _virtualenv.py file
        virtualenv_file = venv_path / "_virtualenv.py"
        source_file = (
            Path(__file__).parent.parent / "src" / "virtualenv" / "create" / "via_global_ref" / "_virtualenv.py"
        )

        if not source_file.exists():
            return  # Skip test if source file doesn't exist

        content = source_file.read_text(encoding="utf-8")
        virtualenv_file.write_text(content, encoding="utf-8")

        # Create the _virtualenv.pth file
        pth_file = venv_path / "_virtualenv.pth"
        pth_file.write_text("import _virtualenv", encoding="utf-8")

        # Simulate the race condition by alternating between importing and overwriting
        errors = []
        for _ in range(5):
            # Overwrite the file
            virtualenv_file.write_text(content, encoding="utf-8")

            # Try to import it
            sys.path.insert(0, str(venv_path))
            try:
                if "_virtualenv" in sys.modules:
                    del sys.modules["_virtualenv"]

                import _virtualenv  # noqa: F401, PLC0415

                # Try to trigger find_spec
                try:
                    importlib.util.find_spec("distutils.dist")
                except NameError as e:
                    if "_DISTUTILS_PATCH" in str(e):
                        errors.append(str(e))
            finally:
                if str(venv_path) in sys.path:
                    sys.path.remove(str(venv_path))

        # Clean up
        if "_virtualenv" in sys.modules:
            del sys.modules["_virtualenv"]

        assert not errors, f"Race condition detected: {errors}"
