from __future__ import annotations

import pytest

from virtualenv.seed.wheels.acquire import find_compatible_in_house
from virtualenv.seed.wheels.embed import BUNDLE_FOLDER, MAX, get_embed_wheel


@pytest.mark.parametrize("version", [pytest.param(None, id="none"), pytest.param("", id="empty")])
def test_find_latest(for_py_version, version: str | None) -> None:
    result = find_compatible_in_house("setuptools", version, for_py_version, BUNDLE_FOLDER)
    expected = get_embed_wheel("setuptools", for_py_version)
    assert result.path == expected.path


def test_find_exact(for_py_version) -> None:
    expected = get_embed_wheel("setuptools", for_py_version)
    result = find_compatible_in_house("setuptools", f"=={expected.version}", for_py_version, BUNDLE_FOLDER)
    assert result.path == expected.path


def test_find_bad_spec() -> None:
    with pytest.raises(ValueError, match="bad"):
        find_compatible_in_house("setuptools", "bad", MAX, BUNDLE_FOLDER)
