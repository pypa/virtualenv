from __future__ import annotations

import zipfile
from typing import TYPE_CHECKING

import pytest

from virtualenv.seed.wheels.embed import MAX, MIN, get_embed_wheel
from virtualenv.seed.wheels.util import Wheel, discover_wheels

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path


@pytest.mark.parametrize(
    "distribution",
    [pytest.param("pip", id="pip"), pytest.param("setuptools", id="setuptools")],
)
def test_embed_wheel_below_oldest_supported_is_missing(distribution: str) -> None:
    assert get_embed_wheel(distribution, "3.8") is None


def test_embed_wheel_oldest_supported_is_present() -> None:
    assert get_embed_wheel("pip", MIN) is not None


def test_embed_wheel_future_version_reuses_newest() -> None:
    assert str(get_embed_wheel("pip", "3.99")) == str(get_embed_wheel("pip", MAX))


def test_bad_as_version_tuple() -> None:
    with pytest.raises(ValueError, match="bad"):
        Wheel.as_version_tuple("bad")


def test_wheel_not_support() -> None:
    assert get_embed_wheel("setuptools", MAX).support_py("3.3") is False


def test_wheel_repr() -> None:
    wheel = get_embed_wheel("setuptools", MAX)
    assert str(wheel.path) in repr(wheel)


def test_unknown_distribution() -> None:
    assert get_embed_wheel("unknown", MAX) is None


@pytest.mark.parametrize(
    ("requires", "py_version", "expected"),
    [
        pytest.param("~=3.9", "3.9", True, id="compatible-release-same-minor"),
        pytest.param("~=3.9", "3.14", True, id="compatible-release-later-minor"),
        pytest.param("~=3.9", "4.0", False, id="compatible-release-next-major"),
        pytest.param(">=3.10,!=3.11.*", "3.11", False, id="every-clause-must-hold"),
        pytest.param(">=3.10,!=3.11.*", "3.12", True, id="every-clause-holds"),
        pytest.param(">= 3.9 , != 3.10.*", "3.12", True, id="whitespace"),
        pytest.param(">=3.6.*", "3.9", False, id="invalid-specifier-skipped"),
        pytest.param("foo", "3.9", False, id="garbage-skipped"),
    ],
)
def test_support_py(pip_wheel: Callable[[str, str], Wheel], requires: str, py_version: str, expected: bool) -> None:
    assert pip_wheel(f"Requires-Python: {requires}\n", "1.0").support_py(py_version) is expected


@pytest.mark.parametrize(
    ("headers", "py_version", "expected"),
    [
        pytest.param("", "3.9", True, id="no-header"),
        pytest.param("requires-python: >=3.12\n", "3.9", False, id="lowercase-header"),
        pytest.param("Requires-Python: >=3.9,\n <3.10\n", "3.12", False, id="folded-header"),
        pytest.param("\nRequires-Python: >=3.99\n", "3.9", True, id="body-only"),
    ],
)
def test_support_py_reads_header(
    pip_wheel: Callable[[str, str], Wheel], headers: str, py_version: str, expected: bool
) -> None:
    assert pip_wheel(headers, "1.0").support_py(py_version) is expected


def test_discover_wheels_skips_unsupported(tmp_path: Path, pip_wheel: Callable[[str, str], Wheel]) -> None:
    pip_wheel("Requires-Python: >=3.99\n", "2.0")
    pip_wheel("", "1.0")

    assert [wheel.version for wheel in discover_wheels(tmp_path, "pip", None, "3.12")] == ["1.0"]


@pytest.fixture
def pip_wheel(tmp_path: Path) -> Callable[[str, str], Wheel]:
    def build(headers: str, version: str) -> Wheel:
        with zipfile.ZipFile(path := tmp_path / f"pip-{version}-py3-none-any.whl", "w") as zip_file:
            zip_file.writestr(
                f"pip-{version}.dist-info/METADATA", f"Metadata-Version: 2.1\nName: pip\nVersion: {version}\n{headers}"
            )
        return Wheel(path)

    return build
