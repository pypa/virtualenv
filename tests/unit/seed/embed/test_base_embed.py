from __future__ import annotations

import sys
import warnings
from typing import TYPE_CHECKING

import pytest

from virtualenv.run import session_via_cli

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.parametrize(
    ("args", "download"),
    [([], False), (["--no-download"], False), (["--never-download"], False), (["--download"], True)],
)
def test_download_cli_flag(args, download, tmp_path):
    session = session_via_cli([*args, str(tmp_path)])
    assert session.seeder.download is download


@pytest.mark.skipif(sys.version_info[:2] == (3, 8), reason="We still bundle wheels for Python 3.8")
def test_download_deprecated_cli_flag(tmp_path):
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        session_via_cli(["--no-wheel", str(tmp_path)])
    assert len(w) == 1
    assert issubclass(w[-1].category, DeprecationWarning)
    assert str(w[-1].message) == (
        "The --no-wheel option is deprecated. It has no effect for Python >= "
        "3.8 as wheel is no longer bundled in virtualenv."
    )


def test_embed_wheel_versions(tmp_path: Path) -> None:
    session = session_via_cli([str(tmp_path)])
    if sys.version_info[:2] >= (3, 12):
        expected = {"pip": "bundle"}
    elif sys.version_info[:2] >= (3, 9):
        expected = {"pip": "bundle", "setuptools": "bundle"}
    else:
        expected = {"pip": "bundle", "setuptools": "bundle", "wheel": "bundle"}
    assert session.seeder.distribution_to_versions() == expected
