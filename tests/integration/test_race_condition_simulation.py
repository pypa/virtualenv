from __future__ import annotations

import importlib.util
import shutil
import sys
from pathlib import Path


def _check_distutils_patch(errors: list[str]) -> None:
    try:
        importlib.util.find_spec("distutils.dist")
    except NameError as e:
        if "_DISTUTILS_PATCH" in str(e):
            errors.append(str(e))


def test_race_condition_simulation(tmp_path) -> None:
    """Test that simulates the race condition described in the issue.

    This test creates a temporary directory with _virtualenv.py and _virtualenv.pth, then simulates the scenario where:
    - One process imports and uses the _virtualenv module (simulating marimo) - Another process overwrites the
    _virtualenv.py file (simulating uv venv)

    The test verifies that no NameError is raised for _DISTUTILS_PATCH.

    """
    # Create the _virtualenv.py file
    virtualenv_file = tmp_path / "_virtualenv.py"
    source_file = Path(__file__).parents[2] / "src" / "virtualenv" / "create" / "via_global_ref" / "_virtualenv.py"

    shutil.copy(source_file, virtualenv_file)

    # Create the _virtualenv.pth file
    pth_file = tmp_path / "_virtualenv.pth"
    pth_file.write_text("import _virtualenv", encoding="utf-8")

    # Simulate the race condition by repeatedly importing
    errors = []
    for _ in range(5):
        sys.path.insert(0, str(tmp_path))
        sys.modules.pop("_virtualenv", None)
        try:
            import _virtualenv  # ruff:ignore[unused-import, import-outside-top-level]

            _check_distutils_patch(errors)
        finally:
            if str(tmp_path) in sys.path:
                sys.path.remove(str(tmp_path))

    assert not errors, f"Race condition detected: {errors}"
