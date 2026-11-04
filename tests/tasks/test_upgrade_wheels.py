from __future__ import annotations

import runpy
import shutil
from pathlib import Path
from typing import Final

import pytest

ROOT: Final[Path] = Path(__file__).parents[2]


@pytest.fixture
def upgrade_script(tmp_path: Path) -> Path:
    # run a copy so the fragment lands under tmp_path rather than the checkout's docs/changelog
    script = tmp_path / "tasks" / "upgrade_wheels.py"
    script.parent.mkdir()
    shutil.copy(ROOT / "tasks" / "upgrade_wheels.py", script)
    return script


@pytest.mark.parametrize(
    ("added", "removed", "expected"),
    [
        pytest.param(
            {"pip": ["26.3"]},
            {"pip": ["26.2.2"]},
            "Upgrade embedded wheels: pip to ``26.3`` from ``26.2.2``.",
            id="replace",
        ),
        pytest.param(
            {"setuptools": ["84.0.0"]}, {}, "Upgrade embedded wheels: setuptools to ``84.0.0``.", id="new-only"
        ),
        pytest.param({}, {"wheel": ["0.45.0"]}, "Removed wheel of ``0.45.0``.", id="removed-only"),
        pytest.param(
            {"pip": ["26.3"], "setuptools": ["84.0.0"]},
            {"pip": ["26.2.2"], "setuptools": ["83.0.0"]},
            "Upgrade embedded wheels: pip to ``26.3`` from ``26.2.2``, setuptools to ``84.0.0`` from ``83.0.0``.",
            id="several-replaced",
        ),
        pytest.param(
            {"pip": ["26.3"]},
            {"setuptools": ["83.0.0"]},
            "Upgrade embedded wheels: pip to ``26.3``. Removed setuptools of ``83.0.0``.",
            id="upgrade-and-removed",
        ),
    ],
)
def test_changelog_fragment_is_prose(
    upgrade_script: Path, added: dict[str, list[str]], removed: dict[str, list[str]], expected: str
) -> None:
    runpy.run_path(str(upgrade_script))["_write_changelog"](added, removed)

    fragment = upgrade_script.parents[1] / "docs" / "changelog" / "embedded-wheels.bugfix.rst"
    assert fragment.read_text(encoding="utf-8") == f"{expected}\n"


def test_changelog_fragment_skipped_without_changes(upgrade_script: Path) -> None:
    runpy.run_path(str(upgrade_script))["_write_changelog"]({}, {})

    assert not (upgrade_script.parents[1] / "docs").exists()
