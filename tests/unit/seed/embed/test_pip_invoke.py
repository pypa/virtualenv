from __future__ import annotations

import os
import subprocess
import sys
from shutil import copytree
from typing import TYPE_CHECKING, Final
from zipfile import ZipFile

import pytest

from virtualenv.info import fs_supports_symlink
from virtualenv.run import cli_run
from virtualenv.seed.wheels.embed import BUNDLE_FOLDER, BUNDLE_SUPPORT, get_embed_wheel
from virtualenv.util.path import safe_delete

if TYPE_CHECKING:
    from pathlib import Path

    from pytest_mock import MockerFixture

    from virtualenv.run.session import Session


@pytest.mark.skipif(not fs_supports_symlink(), reason="symlinks are unavailable")
def test_pip_reseed_keeps_shared_image(linked_seed: Session) -> None:
    package: Final = linked_seed.creator.purelib / "pip"
    image: Final = package.resolve().parent
    before: Final = {
        str(path.relative_to(image)): (path.read_bytes(), path.stat().st_mode)
        for path in image.rglob("*")
        if path.is_file()
    }
    cli_run([str(linked_seed.creator.dest), "--seeder", "pip", "--pip", "embed", "--no-periodic-update"])
    assert {
        str(path.relative_to(image)): (path.read_bytes(), path.stat().st_mode)
        for path in image.rglob("*")
        if path.is_file()
    } == before


@pytest.mark.skipif(not fs_supports_symlink(), reason="symlinks are unavailable")
def test_pip_reseed_installs_local_package(linked_seed: Session) -> None:
    cli_run([str(linked_seed.creator.dest), "--seeder", "pip", "--pip", "embed", "--no-periodic-update"])
    result: Final = subprocess.run(
        [str(linked_seed.creator.exe), "-I", "-m", "pip", "--version"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    assert not (linked_seed.creator.purelib / "pip").is_symlink()
    assert os.path.normcase(str(linked_seed.creator.purelib)) in os.path.normcase(result.stdout)


@pytest.mark.skipif(not fs_supports_symlink(), reason="symlinks are unavailable")
def test_pip_reseed_keeps_unrelated_launcher(linked_seed: Session) -> None:
    unrelated: Final = linked_seed.creator.script_dir / "unrelated-tool"
    unrelated.symlink_to(linked_seed.creator.dest / "missing-tool")
    cli_run([str(linked_seed.creator.dest), "--seeder", "pip", "--pip", "embed", "--no-periodic-update"])
    assert (unrelated.is_symlink(), unrelated.exists()) == (True, False)


@pytest.mark.skipif(not fs_supports_symlink(), reason="symlinks are unavailable")
@pytest.mark.parametrize("name", [pytest.param("__main__.py", id="file"), pytest.param("_internal", id="directory")])
def test_pip_reseed_replaces_nested_link(linked_seed: Session, name: str) -> None:
    package: Final = linked_seed.creator.purelib / "pip"
    source: Final = package.resolve()
    package.unlink()
    copytree(source, package)
    for path in package.rglob("*"):
        if path.is_file():
            path.chmod(0o600)
    entry: Final = package / name
    directory: Final = entry.is_dir()
    if directory:
        safe_delete(entry)
    else:
        entry.unlink()
    entry.symlink_to(source / name, target_is_directory=directory)
    cli_run([str(linked_seed.creator.dest), "--seeder", "pip", "--pip", "embed", "--no-periodic-update"])
    assert (entry.exists(), entry.is_symlink()) == (True, False)


@pytest.mark.skipif(not fs_supports_symlink(), reason="symlinks are unavailable")
def test_pip_reseed_replaces_launcher_link(linked_seed: Session) -> None:
    launcher: Final = linked_seed.creator.script_dir / ("pip.exe" if os.name == "nt" else "pip")
    launcher.unlink()
    missing: Final = linked_seed.creator.dest / "missing-launcher"
    launcher.symlink_to(missing)
    cli_run([str(linked_seed.creator.dest), "--seeder", "pip", "--pip", "embed", "--no-periodic-update"])
    assert (launcher.is_file(), launcher.is_symlink(), missing.exists()) == (True, False, False)


@pytest.mark.parametrize(
    "invalid", [pytest.param("entry", id="package-name"), pytest.param("script", id="script-name")]
)
def test_pip_reseed_rejects_invalid_wheel_names(tmp_path: Path, invalid: str) -> None:
    with ZipFile(tmp_path / "pip-99.0-py3-none-any.whl", "w") as archive:
        archive.writestr("pip-99.0.dist-info/METADATA", "Name: pip\nVersion: 99.0\n")
        if invalid == "entry":
            archive.writestr("./", "")
        else:
            archive.writestr("pip-99.0.dist-info/entry_points.txt", "[console_scripts]\n. = pip:main\n")
    with pytest.raises(RuntimeError, match=f"invalid seed wheel {invalid}"):
        cli_run([
            str(tmp_path / "env"),
            "--seeder",
            "pip",
            "--pip",
            "99.0",
            "--extra-search-dir",
            str(tmp_path),
            "--no-download",
            "--no-periodic-update",
        ])


def test_pip_reseed_reports_process_failure(tmp_path: Path, mocker: MockerFixture) -> None:
    process: Final = mocker.patch("virtualenv.seed.embed.pip_invoke.Popen", autospec=True)
    process.return_value.configure_mock(returncode=7)
    with pytest.raises(RuntimeError, match="failed seed with code 7"):
        cli_run([str(tmp_path / "env"), "--seeder", "pip", "--pip", "embed", "--no-periodic-update"])


def test_pip_reseed_reports_missing_wheel(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="could not get wheel for distribution pip"):
        cli_run([str(tmp_path / "env"), "--seeder", "pip", "--pip", "99.1234", "--no-download", "--no-periodic-update"])


@pytest.fixture
def linked_seed(tmp_path: Path, current_fastest: str) -> Session:
    return cli_run([
        str(tmp_path / "env"),
        "--creator",
        current_fastest,
        "--pip",
        "embed",
        "--no-periodic-update",
        "--symlink-app-data",
        "--app-data",
        str(tmp_path / "cache"),
    ])


@pytest.mark.parametrize("safe_path", [pytest.param("", id="default"), pytest.param("1", id="safe-path")])
def test_pip_invoke_uses_selected_wheel(
    tmp_path: Path, current_fastest: str, monkeypatch: pytest.MonkeyPatch, safe_path: str
) -> None:
    monkeypatch.setenv("PYTHONSAFEPATH", safe_path)
    (tmp_path / "pip").mkdir()
    (tmp_path / "pip" / "__init__.py").write_text("raise SystemExit('imported from the working directory')", "utf-8")
    monkeypatch.chdir(tmp_path)
    session: Final = cli_run([
        str(tmp_path / "env"),
        "--creator",
        current_fastest,
        "--seeder",
        "pip",
        "--pip",
        "embed",
        "--no-periodic-update",
    ])
    result: Final = subprocess.run(
        [str(session.creator.exe), "-I", "-m", "pip", "--version"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    assert os.path.normcase(str(session.creator.purelib)) in os.path.normcase(result.stdout)


@pytest.mark.parametrize(
    "excluded",
    [pytest.param("pip", id="no-pip"), pytest.param("setuptools", id="no-setuptools"), pytest.param("", id="all")],
)
def test_base_bootstrap_via_pip_invoke(tmp_path: Path, current_fastest: str, excluded: str) -> None:
    command: Final = [
        "--seeder",
        "pip",
        str(tmp_path / "env"),
        "--download",
        "--creator",
        current_fastest,
        "--pip",
        "embed",
        "--setuptools",
        "embed",
        "--no-periodic-update",
    ]
    if excluded:
        command.append(f"--no-{excluded}")
    session: Final = cli_run(command)
    assert {path.name for path in session.creator.purelib.iterdir()} & {"pip", "setuptools"} == {
        "pip",
        "setuptools",
    } - {excluded}


def test_pip_invoke_reports_unavailable_wheel(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="could not get wheel for distribution pip"):
        cli_run([
            str(tmp_path / "env"),
            "--seeder",
            "pip",
            "--pip",
            "0.0.0",
            "--no-download",
            "--no-periodic-update",
        ])


@pytest.mark.usefixtures("_no_coverage")
def test_pip_invoke_freeze_uses_version_pin(tmp_path: Path) -> None:
    session: Final = cli_run([
        str(tmp_path / "env"),
        "--seeder",
        "pip",
        "--pip",
        "embed",
        "--no-setuptools",
        "--no-periodic-update",
    ])
    result: Final = subprocess.run(
        [str(session.creator.exe), "-I", "-m", "pip", "freeze", "--all"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    version: Final = get_embed_wheel("pip", f"{sys.version_info.major}.{sys.version_info.minor}").version
    assert f"pip=={version}" in result.stdout.splitlines()


@pytest.mark.skipif(not fs_supports_symlink(), reason="symlinks are unavailable")
@pytest.mark.skipif(sys.version_info < (3, 10), reason="requires two compatible bundled pip versions")
def test_pip_reseed_removes_previous_version_metadata(tmp_path: Path) -> None:
    old: Final = BUNDLE_SUPPORT["3.9"]["pip"].split("-")[1]
    session: Final = cli_run([
        str(tmp_path / "env"),
        "--pip",
        old,
        "--extra-search-dir",
        str(BUNDLE_FOLDER),
        "--symlink-app-data",
        "--no-periodic-update",
        "--app-data",
        str(tmp_path / "cache"),
    ])
    cli_run([str(session.creator.dest), "--seeder", "pip", "--pip", "embed", "--no-periodic-update"])
    expected: Final = BUNDLE_SUPPORT[f"{sys.version_info.major}.{sys.version_info.minor}"]["pip"].split("-")[1]
    assert sorted(entry.name for entry in session.creator.purelib.glob("pip-*.dist-info")) == [
        f"pip-{expected}.dist-info",
    ]
    assert not list(session.creator.purelib.glob(f"pip-{old}.virtualenv"))
