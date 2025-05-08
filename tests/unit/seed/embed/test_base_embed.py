from __future__ import annotations

import sys
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


@pytest.mark.skipif(sys.version_info[:2] == (3, 8), reason="We still bundle wheel for Python 3.8")
@pytest.mark.parametrize("flag", ["--no-wheel", "--wheel=none", "--wheel=embed", "--wheel=bundle"])
def test_wheel_cli_flags_do_nothing(tmp_path, flag):
    session = session_via_cli([flag, str(tmp_path)])
    if sys.version_info[:2] >= (3, 12):
        expected = {"pip": "bundle"}
    else:
        expected = {"pip": "bundle", "setuptools": "bundle"}
    assert session.seeder.distribution_to_versions() == expected


@pytest.mark.skipif(sys.version_info[:2] == (3, 8), reason="We still bundle wheel for Python 3.8")
@pytest.mark.parametrize("flag", ["--no-wheel", "--wheel=none", "--wheel=embed", "--wheel=bundle"])
def test_wheel_cli_flags_warn(tmp_path, flag, capsys):
    session_via_cli([flag, str(tmp_path)])
    out, err = capsys.readouterr()
    assert "The --no-wheel and --wheel options are deprecated." in out + err


@pytest.mark.skipif(sys.version_info[:2] == (3, 8), reason="We still bundle wheel for Python 3.8")
def test_unused_wheel_cli_flags_dont_warn(tmp_path, capsys):
    session_via_cli([str(tmp_path)])
    out, err = capsys.readouterr()
    assert "The --no-wheel and --wheel options are deprecated." not in out + err


@pytest.mark.skipif(sys.version_info[:2] != (3, 8), reason="We only bundle wheel for Python 3.8")
@pytest.mark.parametrize("flag", ["--no-wheel", "--wheel=none", "--wheel=embed", "--wheel=bundle"])
def test_wheel_cli_flags_dont_warn_on_38(tmp_path, flag, capsys):
    session_via_cli([flag, str(tmp_path)])
    out, err = capsys.readouterr()
    assert "The --no-wheel and --wheel options are deprecated." not in out + err


def test_embed_wheel_versions(tmp_path: Path) -> None:
    session = session_via_cli([str(tmp_path)])
    if sys.version_info[:2] >= (3, 12):
        expected = {"pip": "bundle"}
    elif sys.version_info[:2] >= (3, 9):
        expected = {"pip": "bundle", "setuptools": "bundle"}
    else:
        expected = {"pip": "bundle", "setuptools": "bundle", "wheel": "bundle"}
    assert session.seeder.distribution_to_versions() == expected
