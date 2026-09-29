from __future__ import annotations

import zipfile
from typing import TYPE_CHECKING

import pytest

from virtualenv.seed.wheels.acquire import find_compatible_in_house
from virtualenv.seed.wheels.embed import BUNDLE_FOLDER, MAX, get_embed_wheel
from virtualenv.seed.wheels.util import Wheel

if TYPE_CHECKING:
    from pathlib import Path


def _make_wheel(folder: Path, filename: str) -> Path:
    """Write a minimal but valid wheel so discover_wheels can read its METADATA."""
    distribution, version = filename.split("-", maxsplit=1)[0], filename.split("-")[1]
    dist_info = f"{distribution}-{version}.dist-info"
    with zipfile.ZipFile(folder / filename, "w") as zip_file:
        zip_file.writestr(
            f"{dist_info}/METADATA",
            f"Metadata-Version: 2.1\nName: {distribution}\nVersion: {version}\nRequires-Python: >=3.9\n",
        )
        zip_file.writestr(f"{distribution}/__init__.py", "")
    return folder / filename


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


def test_find_exact_prerelease(tmp_path: Path, for_py_version: str) -> None:
    """A pinned pre-release that is present in the house must be found, not a different wheel."""
    _make_wheel(tmp_path, "pip-26.1.5-py3-none-any.whl")
    _make_wheel(tmp_path, "pip-26.2-py3-none-any.whl")
    expected = _make_wheel(tmp_path, "pip-26.2.1rc1-py3-none-any.whl")

    result = find_compatible_in_house("pip", "==26.2.1rc1", for_py_version, tmp_path)

    assert result is not None
    assert result.path == expected


def test_version_tuple_keeps_prerelease_order() -> None:
    """A pre-release sorts below the release it precedes, not equal to an unrelated shorter version."""
    assert Wheel.as_version_tuple("26.2.1rc1") < Wheel.as_version_tuple("26.2.1")
    assert Wheel.as_version_tuple("26.2") < Wheel.as_version_tuple("26.2.1rc1")
    assert Wheel.as_version_tuple("26.2.1rc1") != Wheel.as_version_tuple("26.2")
    assert Wheel.as_version_tuple("26.2.1") > Wheel.as_version_tuple("26.2.1rc1")
