from __future__ import annotations

import json
import runpy
import subprocess
from io import BytesIO
from pathlib import Path
from typing import TYPE_CHECKING, Final
from urllib.error import URLError

import pytest

if TYPE_CHECKING:
    from collections.abc import Callable

    from pytest_mock import MockerFixture


@pytest.fixture
def wheel_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, time_freeze: Callable[[str], None]) -> Path:
    monkeypatch.chdir(tmp_path)
    time_freeze("2026-09-21T00:00:00+00:00")
    embed: Final[Path] = tmp_path / "src" / "virtualenv" / "seed" / "wheels" / "embed"
    embed.mkdir(parents=True)
    (embed / "pip-1-py3-none-any.whl").write_bytes(b"old")
    subprocess.run(["git", "init", "--quiet"], check=True)
    subprocess.run(["git", "add", "."], check=True)
    subprocess.run(
        ["git", "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-qm", "initial"], check=True
    )
    return embed


@pytest.fixture
def check_age(capsys: pytest.CaptureFixture[str]) -> Callable[[], str]:
    def invoke() -> str:
        runpy.run_path(str(Path(__file__).parents[2] / "tasks" / "check_wheel_age.py"), run_name="__main__")
        return capsys.readouterr().out

    return invoke


@pytest.mark.parametrize(
    "wheel",
    [
        pytest.param(("pip-2-py3-none-any.whl", "pip/2"), id="simple-name"),
        pytest.param(("importlib_metadata-8.7.0-py3-none-any.whl", "importlib_metadata/8.7.0"), id="normalized-name"),
        pytest.param(("importlib_metadata-8.7.0-1-py3-none-any.whl", "importlib_metadata/8.7.0"), id="build-tag"),
    ],
)
@pytest.mark.parametrize(
    "age",
    [
        pytest.param(("2026-09-13T00:00:00Z", "skip=false\n"), id="old"),
        pytest.param(("2026-09-14T00:00:00+00:00", "skip=false\n"), id="seven-days"),
        pytest.param(("2026-09-15T00:00:00Z", "skip=true\n"), id="new"),
    ],
)
def test_new_wheel_age(
    wheel_repo: Path,
    mocker: MockerFixture,
    check_age: Callable[[], str],
    age: tuple[str, str],
    wheel: tuple[str, str],
) -> None:
    (wheel_repo / "pip-1-py3-none-any.whl").unlink()
    (wheel_repo / wheel[0]).write_bytes(b"new")
    request = mocker.patch(
        "urllib.request.urlopen",
        autospec=True,
        return_value=BytesIO(
            json.dumps({
                "urls": [
                    {"filename": "pip-2.tar.gz", "upload_time_iso_8601": "2020-01-01T00:00:00Z"},
                    {"filename": wheel[0], "upload_time_iso_8601": age[0]},
                ]
            }).encode()
        ),
    )
    assert check_age() == age[1]
    request.assert_called_once_with(f"https://pypi.org/pypi/{wheel[1]}/json", timeout=30)


@pytest.mark.parametrize("staged", [pytest.param(False, id="untracked"), pytest.param(True, id="staged")])
def test_missing_wheel_metadata(
    wheel_repo: Path, mocker: MockerFixture, check_age: Callable[[], str], staged: bool
) -> None:
    (wheel_repo / "pip-2-py3-none-any.whl").write_bytes(b"new")
    if staged:
        subprocess.run(["git", "add", "."], check=True)
    mocker.patch("urllib.request.urlopen", autospec=True, return_value=BytesIO(b'{"urls": []}'))
    with pytest.raises(SystemExit, match=r"PyPI has no upload information for pip-2-py3-none-any\.whl"):
        check_age()


def test_metadata_network_failure(wheel_repo: Path, mocker: MockerFixture, check_age: Callable[[], str]) -> None:
    (wheel_repo / "pip-2-py3-none-any.whl").write_bytes(b"new")
    mocker.patch("urllib.request.urlopen", autospec=True, side_effect=URLError("unavailable"))
    with pytest.raises(URLError, match="unavailable"):
        check_age()


def test_removed_wheels_need_no_age_check(wheel_repo: Path, check_age: Callable[[], str]) -> None:
    (wheel_repo / "pip-1-py3-none-any.whl").unlink()
    assert check_age() == "skip=false\n"


def test_missing_git(monkeypatch: pytest.MonkeyPatch, check_age: Callable[[], str]) -> None:
    monkeypatch.setenv("PATH", "")
    with pytest.raises(SystemExit, match="git is required"):
        check_age()
