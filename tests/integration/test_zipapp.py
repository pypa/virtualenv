from __future__ import annotations

import hashlib
import importlib.util
import os
import shutil
import subprocess
import sys
import zipfile
from contextlib import suppress
from pathlib import Path
from typing import TYPE_CHECKING, Final

import packaging
import pytest
from python_discovery import PythonInfo

from virtualenv.app_data import AppDataDiskFolder
from virtualenv.info import fs_supports_symlink
from virtualenv.run import cli_run
from virtualenv.seed.wheels.periodic_update import trigger_update
from virtualenv.version import __version__

if TYPE_CHECKING:
    from collections.abc import Callable
    from importlib.machinery import ModuleSpec
    from types import ModuleType

    from pytest_mock import MockerFixture, MockType

    from tasks.make_zipapp import LockedPackage

_HERE: Final[Path] = Path(__file__).parent
_CURRENT: Final[PythonInfo] = PythonInfo.current_system()
# Repackaged sdists omit the zipapp build sources.
_ZIPAPP_MAIN: Final[ModuleType] = pytest.importorskip("tasks.__main__zipapp")


@pytest.fixture(scope="session")
def zipapp_build_env(tmp_path_factory):
    create_env_path = None
    if _CURRENT.implementation not in {"PyPy", "GraalPy"}:
        exe = _CURRENT.executable  # guaranteed to contain a recent enough pip (tox.ini)
    else:
        create_env_path = tmp_path_factory.mktemp("zipapp-create-env")
        exe, found = None, False
        # prefer CPython as builder as pypy is slow
        for impl in ["cpython", ""]:
            for threaded in ["", "t"]:
                # 3.11 brings tomllib, so the build script needs only packaging
                for version in range(15, 10, -1):
                    with suppress(Exception):
                        # create a virtual environment which is also guaranteed to contain a recent enough pip (bundled)
                        session = cli_run(
                            [
                                "-vvv",
                                "-p",
                                f"{impl}3.{version}{threaded}",
                                "--activators",
                                "",
                                str(create_env_path),
                                "--no-download",
                                "--no-periodic-update",
                            ],
                        )
                        exe = str(session.creator.exe)
                        purelib = session.creator.purelib
                        found = True
                        break
                if found:
                    break
            if found:
                break
        else:
            msg = "could not find a python to build zipapp"
            raise RuntimeError(msg)
        # packaging is pure Python, so the copy the tests run with works in the builder without reaching an index
        shutil.copytree(Path(packaging.__file__).parent, purelib / "packaging")
    yield exe
    if create_env_path is not None:
        shutil.rmtree(str(create_env_path))


@pytest.fixture(scope="session")
def zipapp(zipapp_build_env, tmp_path_factory):
    into = tmp_path_factory.mktemp("zipapp")
    filename = into / "virtualenv.pyz"
    cmd = [zipapp_build_env, "-m", "tasks.make_zipapp", "--dest", str(filename)]
    # bundle the wheel tox built and installed, as building from source downloads the build backend
    if (wheel := _tox_built_wheel(os.environ.get("ZIPAPP_WHEEL_DIR"))) is not None:
        shutil.copy2(wheel, into)
        cmd.extend(["--wheel-dir", str(into)])
    subprocess.run([*cmd, *_wheel_cache()], check=True, timeout=300, cwd=_HERE.parent.parent)
    yield filename
    shutil.rmtree(str(into))


def _tox_built_wheel(dist: str | None) -> Path | None:
    if dist is None or not (wheel := Path(dist) / f"virtualenv-{__version__}-py3-none-any.whl").is_file():
        return None
    # an editable install, as tox's dev environment makes, writes a wheel of the same name that holds only a .pth file
    try:
        with zipfile.ZipFile(wheel) as archive:
            return wheel if "virtualenv/__init__.py" in archive.namelist() else None
    except zipfile.BadZipFile:
        return None


def _wheel_cache() -> list[str]:
    # tox turns on the cache CI restores into .tox/zipapp-wheels, so the build bundles the locked wheels offline
    return ["--wheel-cache"] if os.environ.get("ZIPAPP_WHEEL_CACHE") else []


@pytest.fixture(scope="session")
def zipapp_test_env(tmp_path_factory):
    base_path = tmp_path_factory.mktemp("zipapp-test")
    session = cli_run(["-v", "--activators", "", "--without-pip", str(base_path / "env"), "--no-periodic-update"])
    yield session.creator.exe
    shutil.rmtree(str(base_path))


@pytest.mark.timeout(600)
def test_zipapp_loader_context(zipapp: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("tasks.__main__zipapp.ABS_HERE", str(zipapp))
    monkeypatch.delitem(sys.modules, "filelock", raising=False)
    with _ZIPAPP_MAIN.VersionedFindLoad():
        spec: Final[ModuleSpec | None] = importlib.util.find_spec("filelock")
        assert spec is not None
        assert spec.origin is not None
        assert spec.origin.startswith(str(zipapp))
    restored: Final[ModuleSpec | None] = importlib.util.find_spec("filelock")
    assert restored is not None
    assert restored.origin is not None
    assert not restored.origin.startswith(str(zipapp))


@pytest.mark.timeout(600)
def test_zipapp_version(zipapp: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("tasks.__main__zipapp.ABS_HERE", str(zipapp))
    monkeypatch.setattr(sys, "argv", [str(zipapp), "--version"])
    with pytest.raises(SystemExit) as context:
        _ZIPAPP_MAIN._run()  # ruff:ignore[private-member-access]  # the script entry point is private to the module
    assert context.value.code == 0


@pytest.mark.timeout(600)
def test_zipapp_update_command(
    zipapp: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capfd: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr("virtualenv.seed.wheels.periodic_update.IS_ZIPAPP", True)
    monkeypatch.setattr("virtualenv.seed.wheels.periodic_update.ROOT", str(zipapp))
    monkeypatch.setenv("PIP_NO_INDEX", "1")
    trigger_update(
        "pip",
        f"{sys.version_info.major}.{sys.version_info.minor}",
        None,
        [],
        AppDataDiskFolder(str(tmp_path / "data")),
        {**os.environ, "_VIRTUALENV_PERIODIC_UPDATE_INLINE": "1"},
        True,
    )
    assert "done pip" in capfd.readouterr().out


@pytest.mark.timeout(600)
def test_zipapp_update_without_installed_package(zipapp: Path, zipapp_test_env: Path, tmp_path: Path) -> None:
    result: Final[subprocess.CompletedProcess[str]] = subprocess.run(
        [
            str(zipapp_test_env),
            "-I",
            "-c",
            (
                f"import runpy\nwith runpy.run_path({str(zipapp)!r}, run_name='__loader__')['VersionedFindLoad']():\n"
                "    import os, sys\n"
                "    from virtualenv.app_data import AppDataDiskFolder\n"
                "    from virtualenv.seed.wheels.periodic_update import trigger_update\n"
                f"    trigger_update('pip', f'{{sys.version_info.major}}.{{sys.version_info.minor}}', None, [], "
                f"AppDataDiskFolder({str(tmp_path / 'data')!r}), {{**os.environ, '_VIRTUALENV_PERIODIC_UPDATE_INLINE': '1'}}, True)\n"
            ),
        ],
        env={**os.environ, "PIP_NO_INDEX": "1"},
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
        check=True,
    )
    assert "done pip" in result.stdout


@pytest.fixture
# the other fixtures run first for their side effects, the body does not use them
def call_zipapp(zipapp, tmp_path, zipapp_test_env, temp_app_data):  # ruff:ignore[unused-function-argument]
    def _run(*args) -> None:
        cmd = [str(zipapp_test_env), str(zipapp), "-vv", str(tmp_path / "env"), *list(args)]
        subprocess.run(cmd, check=True, timeout=120)

    return _run


@pytest.fixture
# the other fixtures run first for their side effects, the body does not use them
def call_zipapp_symlink(zipapp, tmp_path, zipapp_test_env, temp_app_data):  # ruff:ignore[unused-function-argument]
    def _run(*args) -> None:
        symlinked = zipapp.parent / "symlinked_virtualenv.pyz"
        symlinked.symlink_to(str(zipapp))
        cmd = [str(zipapp_test_env), str(symlinked), "-vv", str(tmp_path / "env"), *list(args)]
        subprocess.run(cmd, check=True, timeout=120)

    return _run


@pytest.mark.timeout(600)
@pytest.mark.skipif(not fs_supports_symlink(), reason="symlink not supported")
def test_zipapp_in_symlink(capsys, call_zipapp_symlink) -> None:
    call_zipapp_symlink("--reset-app-data")
    _out, err = capsys.readouterr()
    assert not err


@pytest.mark.skipif(
    os.name != "posix" or not fs_supports_symlink() or _CURRENT.implementation != "CPython",
    reason="requires CPython to preserve the archive path before running __main__",
)
def test_zipapp_path_with_parent_after_symlink(zipapp: Path, tmp_path: Path) -> None:
    directory: Final[Path] = zipapp.parent / "subdir"
    directory.mkdir(exist_ok=True)
    (tmp_path / "linked").symlink_to(directory, target_is_directory=True)

    result: Final[subprocess.CompletedProcess[str]] = subprocess.run(
        [sys.executable, str(tmp_path / "linked" / ".." / zipapp.name), "--version"],
        capture_output=True,
        check=True,
        encoding="utf-8",
        timeout=60,
    )

    assert result.stdout.startswith(f"virtualenv {__version__} ")


@pytest.mark.timeout(600)
@pytest.mark.slow
@pytest.mark.parametrize("seeder", ["app-data", "pip"])
def test_zipapp_create(call_zipapp, seeder) -> None:
    call_zipapp("--seeder", seeder)


@pytest.mark.timeout(600)
def test_zipapp_bundles_prebuilt_wheel(zipapp_build_env: str, tmp_path: Path) -> None:
    (wheel_dir := tmp_path / "wheels").mkdir()
    with zipfile.ZipFile(wheel_dir / "virtualenv-0-py3-none-any.whl", "w") as wheel:
        wheel.writestr("virtualenv/prebuilt.txt", "prebuilt")
    subprocess.run(
        [
            zipapp_build_env,
            "-m",
            "tasks.make_zipapp",
            "--dest",
            str(pyz := tmp_path / "virtualenv.pyz"),
            "--wheel-dir",
            str(wheel_dir),
            *_wheel_cache(),
        ],
        check=True,
        timeout=300,
        cwd=_HERE.parent.parent,
    )
    with zipfile.ZipFile(pyz) as archive:
        assert archive.read("virtualenv/prebuilt.txt") == b"prebuilt"


@pytest.mark.parametrize(
    ("marker", "expected"),
    [
        pytest.param('"project-runtime" in dependency_groups', True, id="runtime"),
        pytest.param('"build" in dependency_groups', False, id="build-only"),
    ],
)
def test_zipapp_selects_runtime_lock_group(marker: str, expected: bool) -> None:
    assert (
        bool(
            pytest.importorskip("tasks.make_zipapp").python_versions_for({
                "name": "example",
                "version": "1",
                "marker": marker,
            })
        )
        is expected
    )


def test_zipapp_lock_covers_supported_python() -> None:
    versions = pytest.importorskip("tasks.make_zipapp").python_versions_for({
        "name": "example",
        "version": "1",
        "marker": 'python_version >= "3.9"',
    })

    assert "3.15" in versions
    assert "3.8" not in versions


_LOCKED_CONTENT: Final[bytes] = b"wheel"
_LOCKED_NAME: Final[str] = "demo-1.0-py3-none-any.whl"


@pytest.fixture
def make_zipapp() -> ModuleType:
    return pytest.importorskip("tasks.make_zipapp")


@pytest.fixture
def fetch(mocker: MockerFixture, make_zipapp: ModuleType) -> MockType:
    return mocker.patch.object(make_zipapp, "fetch", autospec=True, return_value=_LOCKED_CONTENT)


@pytest.fixture
def download(make_zipapp: ModuleType) -> Callable[[Path], Path]:
    package: Final[LockedPackage] = {
        "name": "demo",
        "version": "1.0",
        "wheels": [
            {
                "url": f"https://files.example/{_LOCKED_NAME}",
                "hashes": {"sha256": hashlib.sha256(_LOCKED_CONTENT).hexdigest()},
            }
        ],
    }
    # only a full zipapp build reaches the download otherwise
    function: Final[Callable[[LockedPackage, Path], Path]] = make_zipapp._download_locked_wheel  # ruff:ignore[private-member-access]
    return lambda into: function(package, into)


def test_locked_wheel_reused_from_cache_when_hash_matches(
    download: Callable[[Path], Path], fetch: MockType, tmp_path: Path
) -> None:
    (tmp_path / _LOCKED_NAME).write_bytes(_LOCKED_CONTENT)

    assert download(tmp_path).read_bytes() == _LOCKED_CONTENT
    fetch.assert_not_called()


def test_locked_wheel_fetched_into_new_cache(download: Callable[[Path], Path], fetch: MockType, tmp_path: Path) -> None:
    cache: Final[Path] = tmp_path / "cache"

    assert download(cache).read_bytes() == _LOCKED_CONTENT
    assert [path.name for path in cache.iterdir()] == [_LOCKED_NAME]
    fetch.assert_called_once_with(f"https://files.example/{_LOCKED_NAME}")


def test_locked_wheel_refetched_over_cached_file_with_other_hash(
    download: Callable[[Path], Path], fetch: MockType, tmp_path: Path
) -> None:
    (tmp_path / _LOCKED_NAME).write_bytes(b"stale")

    assert download(tmp_path).read_bytes() == _LOCKED_CONTENT
    assert [path.name for path in tmp_path.iterdir()] == [_LOCKED_NAME]
    fetch.assert_called_once_with(f"https://files.example/{_LOCKED_NAME}")


def test_locked_wheel_not_matching_lock_is_rejected(
    download: Callable[[Path], Path], fetch: MockType, tmp_path: Path
) -> None:
    fetch.return_value = b"tampered"

    with pytest.raises(RuntimeError, match="records"):
        download(tmp_path)
    assert not list(tmp_path.iterdir())


@pytest.mark.skipif(sys.platform != "win32", reason="only Windows reads a backslash as a separator")
def test_locked_wheel_outside_the_folder_rejected(make_zipapp: ModuleType, fetch: MockType, tmp_path: Path) -> None:
    package: Final[LockedPackage] = {
        "name": "demo",
        "version": "1.0",
        "wheels": [{"url": "https://files.example/..\\demo-1.0-py3-none-any.whl", "hashes": {"sha256": "0"}}],
    }

    with pytest.raises(RuntimeError, match="outside"):
        make_zipapp._download_locked_wheel(package, tmp_path / "cache")  # ruff:ignore[private-member-access]  # no public entry point reaches it
    fetch.assert_not_called()


@pytest.fixture
def peer_holds_wheel_open(fetch: MockType, mocker: MockerFixture, tmp_path: Path) -> Callable[[bytes], None]:
    def written_by_peer(content: bytes) -> None:
        # another build stores its copy while this one downloads, and Windows then refuses to replace the open file
        fetch.side_effect = lambda _url: (tmp_path / _LOCKED_NAME).write_bytes(content) and _LOCKED_CONTENT
        mocker.patch.object(Path, "replace", autospec=True, side_effect=PermissionError("in use"))

    return written_by_peer


def test_locked_wheel_kept_when_another_build_stored_the_same(
    download: Callable[[Path], Path], peer_holds_wheel_open: Callable[[bytes], None], tmp_path: Path
) -> None:
    peer_holds_wheel_open(_LOCKED_CONTENT)

    assert download(tmp_path) == tmp_path / _LOCKED_NAME
    assert [path.name for path in tmp_path.iterdir()] == [_LOCKED_NAME]


def test_locked_wheel_replace_refused_over_other_file_raises(
    download: Callable[[Path], Path], peer_holds_wheel_open: Callable[[bytes], None], tmp_path: Path
) -> None:
    peer_holds_wheel_open(b"other")

    with pytest.raises(PermissionError, match="in use"):
        download(tmp_path)
    assert [path.name for path in tmp_path.iterdir()] == [_LOCKED_NAME]


def test_locked_wheel_replace_refused_without_cached_copy_raises(
    download: Callable[[Path], Path], fetch: MockType, mocker: MockerFixture, tmp_path: Path
) -> None:
    fetch.return_value = _LOCKED_CONTENT
    # a scanner holding the staged file also makes Windows refuse the replace, with no other build involved
    mocker.patch.object(Path, "replace", autospec=True, side_effect=PermissionError("in use"))

    with pytest.raises(PermissionError, match="in use"):
        download(tmp_path)


@pytest.mark.parametrize(
    ("files", "found"),
    [
        pytest.param({"virtualenv/__init__.py": ""}, True, id="built"),
        pytest.param({"_virtualenv_editable.pth": "/src"}, False, id="editable"),
    ],
)
def test_tox_built_wheel_needs_the_package(tmp_path: Path, files: dict[str, str], found: bool) -> None:
    wheel: Final[Path] = tmp_path / f"virtualenv-{__version__}-py3-none-any.whl"
    with zipfile.ZipFile(wheel, "w") as archive:
        for name, content in files.items():
            archive.writestr(name, content)

    assert (_tox_built_wheel(str(tmp_path)) == wheel) is found


@pytest.mark.parametrize("dist", [pytest.param(None, id="no-tox"), pytest.param("missing", id="not-built")])
def test_tox_built_wheel_absent(tmp_path: Path, dist: str | None) -> None:
    assert _tox_built_wheel(dist and str(tmp_path / dist)) is None


def test_tox_built_wheel_corrupt(tmp_path: Path) -> None:
    (tmp_path / f"virtualenv-{__version__}-py3-none-any.whl").write_bytes(b"truncated")

    assert _tox_built_wheel(str(tmp_path)) is None
