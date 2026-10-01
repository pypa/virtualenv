from __future__ import annotations

import zipfile
from typing import TYPE_CHECKING

import pytest

from virtualenv.seed.wheels.embed import MAX, MIN, get_embed_wheel
from virtualenv.seed.wheels.util import Wheel

if TYPE_CHECKING:
    from pathlib import Path


def _wheel_with_requires(folder: Path, filename: str, requires_python: str) -> Wheel:
    """Write a wheel whose METADATA carries the given Requires-Python, then wrap it."""
    distribution, version = filename.split("-", maxsplit=1)[0], filename.split("-")[1]
    dist_info = f"{distribution}-{version}.dist-info"
    with zipfile.ZipFile(folder / filename, "w") as zip_file:
        zip_file.writestr(
            f"{dist_info}/METADATA",
            f"Metadata-Version: 2.1\nName: {distribution}\nVersion: {version}\nRequires-Python: {requires_python}\n",
        )
        zip_file.writestr(f"{distribution}/__init__.py", "")
    return Wheel(folder / filename)


@pytest.mark.parametrize(
    "distribution",
    [pytest.param("pip", id="pip"), pytest.param("setuptools", id="setuptools")],
)
def test_embed_wheel_below_oldest_supported_is_missing(distribution: str) -> None:
    assert get_embed_wheel(distribution, "3.8") is None


def test_embed_wheel_oldest_supported_is_present() -> None:
    assert get_embed_wheel("pip", MIN) is not None


def test_embed_wheel_future_version_reuses_newest() -> None:
    future, newest = get_embed_wheel("pip", "3.99"), get_embed_wheel("pip", MAX)
    assert future is not None
    assert newest is not None
    assert future.name == newest.name


def test_wheel_support_no_python_requires(mocker) -> None:
    wheel = get_embed_wheel("setuptools", for_py_version=None)
    zip_mock = mocker.MagicMock()
    mocker.patch("virtualenv.seed.wheels.util.ZipFile", new=zip_mock)
    zip_mock.return_value.__enter__.return_value.read = lambda _name: b""

    supports = wheel.support_py("3.9")
    assert supports is True


def test_bad_as_version_tuple() -> None:
    with pytest.raises(ValueError, match="bad"):
        Wheel.as_version_tuple("bad")


def test_wheel_not_support() -> None:
    wheel = get_embed_wheel("setuptools", MAX)
    assert wheel.support_py("3.3") is False


def test_wheel_repr() -> None:
    wheel = get_embed_wheel("setuptools", MAX)
    assert str(wheel.path) in repr(wheel)


def test_unknown_distribution() -> None:
    wheel = get_embed_wheel("unknown", MAX)
    assert wheel is None


def test_support_py_honours_compatible_release(tmp_path: Path) -> None:
    """``~=3.9`` is ``>=3.9, ==3.*``, so it covers later minors but not the next major."""
    wheel = _wheel_with_requires(tmp_path, "pip-9.1-py3-none-any.whl", "~=3.9")

    assert wheel.support_py("3.9") is True
    assert wheel.support_py("3.14") is True
    assert wheel.support_py("4.0") is False


def test_support_py_compatible_release_keeps_patch_prefix(tmp_path: Path) -> None:
    """``~=3.10.1`` is ``>=3.10.1, ==3.10.*``, so neither 3.10.0 nor a later minor matches."""
    wheel = _wheel_with_requires(tmp_path, "pip-9.2-py3-none-any.whl", "~=3.10.1")

    assert wheel.support_py("3.10.1") is True
    assert wheel.support_py("3.10") is False
    assert wheel.support_py("3.11") is False


def test_support_py_compares_all_version_components(tmp_path: Path) -> None:
    """A three-part requirement must not be truncated, so ``>=3.9.1`` excludes 3.9.0."""
    wheel = _wheel_with_requires(tmp_path, "pip-9.3-py3-none-any.whl", ">=3.9.1")

    assert wheel.support_py("3.9") is False
    assert wheel.support_py("3.10") is True


def test_support_py_every_requirement_must_hold(tmp_path: Path) -> None:
    """Each clause of a specifier set has to be satisfied, not just the first."""
    wheel = _wheel_with_requires(tmp_path, "pip-9.4-py3-none-any.whl", ">=3.10,~=3.10.1")

    assert wheel.support_py("3.9") is False
    assert wheel.support_py("3.10") is False
    assert wheel.support_py("3.10.1") is True
    assert wheel.support_py("3.11") is False
