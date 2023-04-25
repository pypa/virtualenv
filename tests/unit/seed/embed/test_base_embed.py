from __future__ import annotations

import sys
from pathlib import Path

import pytest

from virtualenv.run import session_via_cli


@pytest.mark.parametrize(
    ("args", "download"),
    [([], False), (["--no-download"], False), (["--never-download"], False), (["--download"], True)],
)
def test_download_cli_flag(args, download, tmp_path):
    session = session_via_cli(args + [str(tmp_path)])
    assert session.seeder.download is download


def test_embed_wheel_versions(tmp_path: Path) -> None:
    session = session_via_cli([str(tmp_path)])
    expected = (
        {"pip": "bundle"}
        if sys.version_info[:2] >= (3, 12)
        else {"pip": "bundle", "setuptools": "bundle", "wheel": "bundle"}
    )
    assert session.seeder.distribution_to_versions() == expected
