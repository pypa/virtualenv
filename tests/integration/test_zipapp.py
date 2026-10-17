from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
import sys
import zipfile
from contextlib import suppress
from pathlib import Path
from typing import Final

import pytest
from python_discovery import PythonInfo

from virtualenv.app_data import AppDataDiskFolder
from virtualenv.info import fs_supports_symlink
from virtualenv.run import cli_run
from virtualenv.seed.wheels.periodic_update import trigger_update

HERE = Path(__file__).parent
CURRENT = PythonInfo.current_system()
# Repackaged sdists omit the zipapp build sources.
_ZIPAPP_MAIN: Final = pytest.importorskip("tasks.__main__zipapp")


@pytest.fixture(scope="session")
def zipapp_build_env(tmp_path_factory):
    create_env_path = None
    if CURRENT.implementation not in {"PyPy", "GraalPy"}:
        exe = CURRENT.executable  # guaranteed to contain a recent enough pip (tox.ini)
    else:
        create_env_path = tmp_path_factory.mktemp("zipapp-create-env")
        exe, found = None, False
        # prefer CPython as builder as pypy is slow
        for impl in ["cpython", ""]:
            for threaded in ["", "t"]:
                for version in range(11, 6, -1):
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
                        found = True
                        break
                if found:
                    break
            if found:
                break
        else:
            msg = "could not find a python to build zipapp"
            raise RuntimeError(msg)
        cmd = [
            str(Path(exe).parent / "pip"),
            "install",
            "pip>=23",
            "packaging>=23",
            "tomli>=2.0.1; python_version<'3.11'",
        ]
        subprocess.run(cmd, check=True, timeout=300)
    yield exe
    if create_env_path is not None:
        shutil.rmtree(str(create_env_path))


@pytest.fixture(scope="session")
def zipapp(zipapp_build_env, tmp_path_factory):
    into = tmp_path_factory.mktemp("zipapp")
    path = HERE.parent.parent / "tasks" / "make_zipapp.py"
    filename = into / "virtualenv.pyz"
    cmd = [zipapp_build_env, str(path), "--dest", str(filename)]
    subprocess.run(cmd, check=True, timeout=300)
    yield filename
    shutil.rmtree(str(into))


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
        spec: Final = importlib.util.find_spec("filelock")
        assert spec is not None
        assert spec.origin is not None
        assert spec.origin.startswith(str(zipapp))
    restored: Final = importlib.util.find_spec("filelock")
    assert restored is not None
    assert restored.origin is not None
    assert not restored.origin.startswith(str(zipapp))


@pytest.mark.timeout(600)
def test_zipapp_version(zipapp: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("tasks.__main__zipapp.ABS_HERE", str(zipapp))
    monkeypatch.setattr(sys, "argv", [str(zipapp), "--version"])
    with pytest.raises(SystemExit) as context:
        _ZIPAPP_MAIN.run()
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
        {"_VIRTUALENV_PERIODIC_UPDATE_INLINE": "1"},
        True,
    )
    assert "done pip" in capfd.readouterr().out


@pytest.mark.timeout(600)
def test_zipapp_update_without_installed_package(zipapp: Path, zipapp_test_env: Path, tmp_path: Path) -> None:
    result: Final = subprocess.run(
        [
            str(zipapp_test_env),
            "-I",
            "-c",
            (
                f"import runpy\nwith runpy.run_path({str(zipapp)!r}, run_name='__loader__')['VersionedFindLoad']():\n"
                "    import sys\n"
                "    from virtualenv.app_data import AppDataDiskFolder\n"
                "    from virtualenv.seed.wheels.periodic_update import trigger_update\n"
                f"    trigger_update('pip', f'{{sys.version_info.major}}.{{sys.version_info.minor}}', None, [], "
                f"AppDataDiskFolder({str(tmp_path / 'data')!r}), {{'_VIRTUALENV_PERIODIC_UPDATE_INLINE': '1'}}, True)\n"
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
def call_zipapp(zipapp, tmp_path, zipapp_test_env, temp_app_data):  # ruff:ignore[unused-function-argument]
    def _run(*args) -> None:
        cmd = [str(zipapp_test_env), str(zipapp), "-vv", str(tmp_path / "env"), *list(args)]
        subprocess.run(cmd, check=True, timeout=120)

    return _run


@pytest.fixture
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
            str(HERE.parent.parent / "tasks" / "make_zipapp.py"),
            "--dest",
            str(pyz := tmp_path / "virtualenv.pyz"),
            "--wheel-dir",
            str(wheel_dir),
        ],
        check=True,
        timeout=300,
    )
    with zipfile.ZipFile(pyz) as archive:
        assert archive.read("virtualenv/prebuilt.txt") == b"prebuilt"
