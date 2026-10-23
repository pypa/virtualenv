from __future__ import annotations

import pytest

from tasks.make_zipapp import python_versions_for


@pytest.mark.parametrize(
    ("marker", "expected"),
    [
        pytest.param('"project-runtime" in dependency_groups', True, id="runtime"),
        pytest.param('"build" in dependency_groups', False, id="build-only"),
    ],
)
def test_zipapp_selects_runtime_lock_group(marker: str, expected: bool) -> None:
    assert bool(python_versions_for({"name": "example", "version": "1", "marker": marker})) is expected


def test_zipapp_lock_covers_supported_python() -> None:
    versions = python_versions_for({"name": "example", "version": "1", "marker": 'python_version >= "3.9"'})

    assert "3.15" in versions
    assert "3.8" not in versions
