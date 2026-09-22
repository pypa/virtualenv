from __future__ import annotations

import json
import runpy
import shutil
import subprocess
import sys
import zipfile
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


@pytest.fixture
def generator_repo(tmp_path: Path) -> Path:
    if sys.version_info[:2] != (3, 14) or sys.implementation.name != "cpython":
        pytest.skip("The upgrade workflow runs its formatter toolchain on CPython 3.14")
    root: Final[Path] = Path(__file__).parents[2]
    (tmp_path / "tasks").mkdir()
    shutil.copyfile(root / "tasks" / "upgrade_wheels.py", tmp_path / "tasks" / "upgrade_wheels.py")
    shutil.copyfile(root / ".pre-commit-config.yaml", tmp_path / ".pre-commit-config.yaml")
    shutil.copyfile(root / "pyproject.toml", tmp_path / "pyproject.toml")
    embed: Final[Path] = tmp_path / "src" / "virtualenv" / "seed" / "wheels" / "embed"
    embed.mkdir(parents=True)
    (embed / "__init__.py").write_text(
        'BUNDLE_SUPPORT = {"3.14": {"pip": "pip-1-py3-none-any.whl"}}\n', encoding="utf-8"
    )
    with zipfile.ZipFile(embed / "pip-1-py3-none-any.whl", "w") as archive:
        archive.writestr("pip-1.dist-info/METADATA", "Name: pip\nVersion: 1\n")
        archive.writestr("pip-1.dist-info/licenses/LICENSE.txt", "Copyright Example\nPermission to redistribute.\n")
    subprocess.run(["git", "init", "--quiet"], cwd=tmp_path, check=True)
    return tmp_path


@pytest.fixture
def regenerate(generator_repo: Path) -> Callable[[], subprocess.CompletedProcess[str]]:
    def invoke() -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "tasks/upgrade_wheels.py", "--regen"],
            cwd=generator_repo,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=True,
        )

    return invoke


def test_generator_converges(generator_repo: Path, regenerate: Callable[[], subprocess.CompletedProcess[str]]) -> None:
    regenerate()
    assert "Copyright Example" in (generator_repo / "THIRD-PARTY-NOTICES.md").read_text(encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=generator_repo, check=True)
    regenerate()
    subprocess.run(
        ["pre-commit", "run", "mdformat", "--files", "THIRD-PARTY-NOTICES.md"],
        cwd=generator_repo,
        check=True,
    )
    assert (
        subprocess.run(["git", "diff", "--exit-code"], cwd=generator_repo, capture_output=True, check=False).returncode
        == 0
    )


def test_generator_updates_license(
    generator_repo: Path, regenerate: Callable[[], subprocess.CompletedProcess[str]]
) -> None:
    regenerate()
    subprocess.run(["git", "add", "."], cwd=generator_repo, check=True)
    wheel: Final[Path] = generator_repo / "src/virtualenv/seed/wheels/embed/pip-1-py3-none-any.whl"
    with zipfile.ZipFile(wheel, "w") as archive:
        archive.writestr("pip-1.dist-info/METADATA", "Name: pip\nVersion: 1\n")
        archive.writestr("pip-1.dist-info/licenses/LICENSE.txt", "Copyright Changed\nPermission to redistribute.\n")
    regenerate()
    assert "Copyright Changed" in (generator_repo / "THIRD-PARTY-NOTICES.md").read_text(encoding="utf-8")


def test_generator_formatter_failure(
    generator_repo: Path, regenerate: Callable[[], subprocess.CompletedProcess[str]]
) -> None:
    (generator_repo / ".pre-commit-config.yaml").write_text("repos: invalid\n", encoding="utf-8")
    with pytest.raises(subprocess.CalledProcessError):
        regenerate()


@pytest.fixture
def apply_patch(wheel_repo: Path) -> Callable[[str, str], subprocess.CompletedProcess[str]]:
    def invoke(filename: str, mode: str = "100644") -> subprocess.CompletedProcess[str]:
        blob: Final[str] = subprocess.run(
            ["git", "hash-object", "-w", "--stdin"],
            input="new\0content",
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=True,
        ).stdout.strip()
        if mode == "000000":
            subprocess.run(["git", "update-index", "--force-remove", filename], check=True)
        else:
            subprocess.run(["git", "update-index", "--add", "--cacheinfo", mode, blob, filename], check=True)
        patch: Final[bytes] = subprocess.run(
            ["git", "diff", "--cached", "--binary"], capture_output=True, check=True
        ).stdout
        subprocess.run(["git", "reset", "-q", "HEAD", "--", filename], check=True)
        patch_file: Final[Path] = wheel_repo.parents[4] / "upgrade.patch"
        patch_file.write_bytes(patch)
        return subprocess.run(
            [sys.executable, str(Path(__file__).parents[2] / "tasks" / "apply_upgrade_patch.py"), str(patch_file)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )

    return invoke


@pytest.mark.parametrize(
    "filename",
    [
        pytest.param("THIRD-PARTY-NOTICES.md", id="notices"),
        pytest.param("docs/changelog/u.bugfix.rst", id="changelog"),
        pytest.param("src/virtualenv/seed/wheels/embed/__init__.py", id="bundle-index"),
        pytest.param("src/virtualenv/seed/wheels/embed/pip-2-py3-none-any.whl", id="wheel"),
    ],
)
def test_upgrade_patch_applies(
    apply_patch: Callable[[str, str], subprocess.CompletedProcess[str]], filename: str
) -> None:
    result: Final = apply_patch(filename, "100644")
    assert (result.returncode, Path(filename).read_bytes()) == (0, b"new\0content")


@pytest.mark.parametrize(
    ("filename", "mode"),
    [
        pytest.param(".github/workflows/release.yaml", "100644", id="workflow"),
        pytest.param("tasks/apply_upgrade_patch.py", "100644", id="validator"),
        pytest.param("src/virtualenv/seed/wheels/embed/subdir/pip.whl", "100644", id="nested-path"),
        pytest.param("THIRD-PARTY-NOTICES.md", "120000", id="symlink"),
        pytest.param("THIRD-PARTY-NOTICES.md", "100755", id="executable"),
    ],
)
def test_upgrade_patch_rejects(
    apply_patch: Callable[[str, str], subprocess.CompletedProcess[str]], filename: str, mode: str
) -> None:
    result: Final = apply_patch(filename, mode)
    assert (result.returncode, Path(filename).exists()) == (1, False)
    assert "unsupported path or file mode" in result.stderr


def test_upgrade_patch_removes_old_wheel(
    wheel_repo: Path, apply_patch: Callable[[str, str], subprocess.CompletedProcess[str]]
) -> None:
    result: Final = apply_patch("src/virtualenv/seed/wheels/embed/pip-1-py3-none-any.whl", "000000")
    assert (result.returncode, (wheel_repo / "pip-1-py3-none-any.whl").exists()) == (0, False)


def test_upgrade_patch_missing_git(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PATH", "")
    with pytest.raises(SystemExit, match="git is required"):
        runpy.run_path(str(Path(__file__).parents[2] / "tasks" / "apply_upgrade_patch.py"), run_name="__main__")
