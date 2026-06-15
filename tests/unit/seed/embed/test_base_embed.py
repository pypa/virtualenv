from __future__ import annotations

import sys
from typing import TYPE_CHECKING, NamedTuple

import pytest

from virtualenv.run import session_via_cli
from virtualenv.seed.embed.pip_invoke import PipInvoke
from virtualenv.seed.embed.via_app_data.via_app_data import FromAppData
from virtualenv.seed.seeder import Seeder
from virtualenv.seed.wheels.embed import MIN, OLDEST_SUPPORTED

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path
    from unittest.mock import MagicMock

    from pytest_mock import MockerFixture

    from virtualenv.seed.embed.base_embed import BaseEmbed


@pytest.mark.parametrize(
    ("args", "download"),
    [([], False), (["--no-download"], False), (["--never-download"], False), (["--download"], True)],
)
def test_download_cli_flag(args, download, tmp_path) -> None:
    session = session_via_cli([*args, str(tmp_path)])
    assert session.seeder.download is download


@pytest.mark.parametrize("flag", ["--no-wheel", "--wheel=none", "--wheel=embed", "--wheel=bundle"])
def test_wheel_cli_flags_do_nothing(tmp_path, flag) -> None:
    session = session_via_cli([flag, str(tmp_path)])
    if sys.version_info[:2] >= (3, 12):
        expected = {"pip": "bundle"}
    else:
        expected = {"pip": "bundle", "setuptools": "bundle"}
    assert session.seeder.distribution_to_versions() == expected


@pytest.mark.parametrize("flag", ["--no-wheel", "--wheel=none", "--wheel=embed", "--wheel=bundle"])
def test_wheel_cli_flags_warn(tmp_path, flag, capsys) -> None:
    session_via_cli([flag, str(tmp_path)])
    out, err = capsys.readouterr()
    assert "the --wheel and --no-wheel options do nothing" in out + err


def test_unused_wheel_cli_flags_dont_warn(tmp_path, capsys) -> None:
    session_via_cli([str(tmp_path)])
    out, err = capsys.readouterr()
    assert "the --wheel and --no-wheel options do nothing" not in out + err


def test_embed_wheel_versions(tmp_path: Path) -> None:
    session = session_via_cli([str(tmp_path)])
    if sys.version_info[:2] >= (3, 12):
        expected = {"pip": "bundle"}
    else:
        expected = {"pip": "bundle", "setuptools": "bundle"}
    assert session.seeder.distribution_to_versions() == expected


BUNDLED_SEEDERS = [pytest.param(FromAppData, id="app-data"), pytest.param(PipInvoke, id="pip")]


@pytest.mark.parametrize("seeder", BUNDLED_SEEDERS)
def test_bundled_seeder_reports_reason_below_floor(
    seeder: type[BaseEmbed], at_version: Callable[[int, int], MagicMock]
) -> None:
    reason = seeder.cannot_seed(at_version(3, 8))
    assert reason is not None
    assert "Python 3.8" in reason
    assert f"Python {MIN}" in reason
    assert "--no-seed" in reason


@pytest.mark.parametrize("seeder", BUNDLED_SEEDERS)
def test_bundled_seeder_has_no_reason_on_oldest_supported(
    seeder: type[BaseEmbed], at_version: Callable[[int, int], MagicMock]
) -> None:
    assert seeder.cannot_seed(at_version(*OLDEST_SUPPORTED)) is None


def test_base_seeder_never_blocks(at_version: Callable[[int, int], MagicMock]) -> None:
    assert Seeder.cannot_seed(at_version(3, 8)) is None


def test_selection_surfaces_the_seeder_reason(tmp_path: Path, mocker: MockerFixture) -> None:
    mocker.patch.object(FromAppData, "cannot_seed", return_value="seeder said no for a specific reason")
    with pytest.raises(RuntimeError, match="seeder said no for a specific reason"):
        session_via_cli([str(tmp_path)])


def test_no_seed_bypasses_capability_check(tmp_path: Path, mocker: MockerFixture) -> None:
    mocker.patch.object(FromAppData, "cannot_seed", return_value="seeder said no")
    assert session_via_cli(["--no-seed", str(tmp_path)]).seeder.enabled is False


@pytest.fixture
def at_version(mocker: MockerFixture) -> Callable[[int, int], MagicMock]:
    def build(major: int, minor: int) -> MagicMock:
        interpreter = mocker.MagicMock()
        interpreter.version_info = _VersionInfo(major, minor)
        return interpreter

    return build


class _VersionInfo(NamedTuple):
    major: int
    minor: int
