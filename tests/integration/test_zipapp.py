from __future__ import annotations

import shutil
import subprocess
from contextlib import suppress
from pathlib import Path

import pytest
from flaky import flaky

from virtualenv.discovery.py_info import PythonInfo
from virtualenv.info import fs_supports_symlink
from virtualenv.run import cli_run

HERE = Path(__file__).parent
CURRENT = PythonInfo.current_system()


@pytest.fixture(scope="session")
def zipapp_build_env(tmp_path_factory):
    create_env_path = None
    if CURRENT.implementation != "PyPy":
        exe = CURRENT.executable  # guaranteed to contain a recent enough pip (tox.ini)
    else:
        create_env_path = tmp_path_factory.mktemp("zipapp-create-env")
        exe, found = None, False
        # prefer CPython as builder as pypy is slow
        for impl in ["cpython", ""]:
            for version in range(11, 6, -1):
                with suppress(Exception):
                    # create a virtual environment which is also guaranteed to contain a recent enough pip (bundled)
                    session = cli_run(
                        [
                            "-vvv",
                            "-p",
                            f"{impl}3.{version}",
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
        else:
            msg = "could not find a python to build zipapp"
            raise RuntimeError(msg)
        cmd = [str(Path(exe).parent / "pip"), "install", "pip>=23", "packaging>=23"]
        subprocess.check_call(cmd)
    yield exe
    if create_env_path is not None:
        shutil.rmtree(str(create_env_path))


@pytest.fixture(scope="session")
def zipapp(zipapp_build_env, tmp_path_factory):
    into = tmp_path_factory.mktemp("zipapp")
    path = HERE.parent.parent / "tasks" / "make_zipapp.py"
    filename = into / "virtualenv.pyz"
    cmd = [zipapp_build_env, str(path), "--dest", str(filename)]
    subprocess.check_call(cmd)
    yield filename
    shutil.rmtree(str(into))


@pytest.fixture(scope="session")
def zipapp_test_env(tmp_path_factory):
    base_path = tmp_path_factory.mktemp("zipapp-test")
    session = cli_run(["-v", "--activators", "", "--without-pip", str(base_path / "env"), "--no-periodic-update"])
    yield session.creator.exe
    shutil.rmtree(str(base_path))


@pytest.fixture
def call_zipapp(zipapp, tmp_path, zipapp_test_env, temp_app_data):  # noqa: ARG001
    def _run(*args):
        cmd = [str(zipapp_test_env), str(zipapp), "-vv", str(tmp_path / "env"), *list(args)]
        subprocess.check_call(cmd)

    return _run


@pytest.fixture
def call_zipapp_symlink(zipapp, tmp_path, zipapp_test_env, temp_app_data):  # noqa: ARG001
    def _run(*args):
        symlinked = zipapp.parent / "symlinked_virtualenv.pyz"
        symlinked.symlink_to(str(zipapp))
        cmd = [str(zipapp_test_env), str(symlinked), "-vv", str(tmp_path / "env"), *list(args)]
        subprocess.check_call(cmd)

    return _run


@pytest.mark.skipif(not fs_supports_symlink(), reason="symlink not supported")
def test_zipapp_in_symlink(capsys, call_zipapp_symlink):
    call_zipapp_symlink("--reset-app-data")
    _out, err = capsys.readouterr()
    assert not err


@flaky(max_runs=2, min_passes=1)
def test_zipapp_help(call_zipapp, capsys):
    call_zipapp("-h")
    _out, err = capsys.readouterr()
    assert not err


@pytest.mark.parametrize("seeder", ["app-data", "pip"])
def test_zipapp_create(call_zipapp, seeder):
    call_zipapp("--seeder", seeder)
