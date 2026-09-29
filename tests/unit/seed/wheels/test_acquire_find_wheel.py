from __future__ import annotations

import zipfile
from typing import TYPE_CHECKING, Final

import pytest

from virtualenv.seed.wheels.acquire import find_compatible_in_house
from virtualenv.seed.wheels.embed import BUNDLE_FOLDER, MAX, get_embed_wheel
from virtualenv.seed.wheels.util import Wheel, discover_wheels

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path


@pytest.mark.parametrize("version", [pytest.param(None, id="none"), pytest.param("", id="empty")])
def test_find_latest(for_py_version: str, version: str | None) -> None:
    result: Final = find_compatible_in_house("setuptools", version, for_py_version, BUNDLE_FOLDER)
    expected: Final = get_embed_wheel("setuptools", for_py_version)
    assert result is not None
    assert expected is not None
    assert result.path == expected.path


def test_find_exact(for_py_version: str) -> None:
    expected: Final = get_embed_wheel("setuptools", for_py_version)
    assert expected is not None
    result: Final = find_compatible_in_house("setuptools", f"=={expected.version}", for_py_version, BUNDLE_FOLDER)
    assert result is not None
    assert result.path == expected.path


@pytest.mark.parametrize("spec", [pytest.param("bad", id="invalid"), pytest.param(">=1", id="unsupported")])
def test_find_bad_spec(spec: str) -> None:
    with pytest.raises(ValueError, match=spec):
        find_compatible_in_house("setuptools", spec, MAX, BUNDLE_FOLDER)


@pytest.mark.parametrize(
    ("other", "requested"),
    [
        pytest.param("26.2", "26.2.1rc1", id="prerelease"),
        pytest.param("26.2.1rc1", "26.2.1rc1.dev2", id="prerelease-dev"),
        pytest.param("26.2.1.post1", "26.2.1.post1.dev2", id="postrelease-dev"),
        pytest.param("26.2.1", "26.2.1.1", id="four-release-components"),
        pytest.param("26.2.1", "26.2.1+local.1", id="local"),
        pytest.param("1!26.2.1", "1!26.2.2", id="epoch"),
    ],
)
@pytest.mark.parametrize("available", [True, False], ids=["present", "missing"])
def test_find_exact_version(
    tmp_path: Path, make_wheel: Callable[[str], Path], other: str, requested: str, available: bool
) -> None:
    make_wheel(other)
    expected: Final = make_wheel(requested) if available else None
    result: Final = find_compatible_in_house("pip", f"=={requested}", "3.14", tmp_path)
    assert (result.path if result else None) == expected


@pytest.mark.parametrize(
    ("older", "newer"),
    [
        pytest.param("26.2", "26.2.1rc1", id="release-before-next-prerelease"),
        pytest.param("26.2.1rc1", "26.2.1", id="prerelease-before-final"),
        pytest.param("26.2.1rc1.dev1", "26.2.1rc1", id="prerelease-dev"),
        pytest.param("26.2.1.post1.dev1", "26.2.1.post1", id="postrelease-dev"),
        pytest.param("26.2.1", "26.2.1.1", id="four-release-components"),
        pytest.param("26.2.1+abc", "26.2.1+1", id="local-numeric-after-text"),
        pytest.param("26.2.1", "1!1.0", id="epoch"),
    ],
)
def test_discover_version_order(tmp_path: Path, make_wheel: Callable[[str], Path], older: str, newer: str) -> None:
    make_wheel(older)
    make_wheel(newer)
    assert [wheel.version for wheel in discover_wheels(tmp_path, "pip", None, "3.14")] == [newer, older]


@pytest.mark.parametrize("version", ["26.2.1", "26.2.1rc1", "26.2.1.post1", "26.2.1.dev1"])
def test_version_tuple_contains_release_numbers(make_wheel: Callable[[str], Path], version: str) -> None:
    assert Wheel(make_wheel(version)).version_tuple == (26, 2, 1)


@pytest.mark.parametrize(
    ("versions", "spec", "expected"),
    [
        pytest.param(("26.2.0", "26.2.1rc1"), "<26.2.1", "26.2.0", id="exclude-bound-prerelease"),
        pytest.param(("26.2.0", "26.2.1rc1"), "<26.2.1rc2", "26.2.1rc1", id="explicit-prerelease-bound"),
        pytest.param(("26.2.1", "26.2.1+local.1"), "==26.2.1", "26.2.1+local.1", id="public-pin"),
        pytest.param(("26.2.1", "26.2.1rc1"), "==26.2.1RC1", "26.2.1rc1", id="normalized-pin"),
    ],
)
def test_find_version_specifier(
    tmp_path: Path, make_wheel: Callable[[str], Path], versions: tuple[str, ...], spec: str, expected: str
) -> None:
    for version in versions:
        make_wheel(version)
    result: Final = find_compatible_in_house("pip", spec, "3.14", tmp_path)
    assert result is not None
    assert result.version == expected


@pytest.fixture
def make_wheel(tmp_path: Path) -> Callable[[str], Path]:
    def build(version: str) -> Path:
        path: Final = tmp_path / f"pip-{version}-py3-none-any.whl"
        with zipfile.ZipFile(path, "w") as wheel:
            wheel.writestr(
                f"pip-{version}.dist-info/METADATA",
                f"Metadata-Version: 2.1\nName: pip\nVersion: {version}\nRequires-Python: >=3.9\n",
            )
        return path

    return build
