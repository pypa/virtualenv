from __future__ import absolute_import, unicode_literals

import shutil
import subprocess
import sys

import pytest
from flaky import flaky

from virtualenv.discovery.py_info import PythonInfo
from virtualenv.run import cli_run
from virtualenv.util.path import Path
from virtualenv.util.six import ensure_text

HERE = Path(__file__).parent
CURRENT = PythonInfo.current_system()


@pytest.fixture(scope="session")
def zipapp_build_env(tmp_path_factory):
    create_env_path = None
    if sys.version_info[0:2] >= (3, 5) and CURRENT.implementation != "PyPy":
        exe = CURRENT.executable  # guaranteed to contain a recent enough pip (tox.ini)
    else:
        create_env_path = tmp_path_factory.mktemp("zipapp-create-env")
        exe, found = None, False
        # prefer CPython as builder as pypy is slow
        for impl in ["cpython", ""]:
            for version in range(8, 4, -1):
                try:
                    # create a virtual environment which is also guaranteed to contain a recent enough pip (bundled)
                    session = cli_run(
                        [
                            "-vvv",
                            "-p",
                            "{}3.{}".format(impl, version),
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
                except Exception:
                    pass
            if found:
                break
        else:
            raise RuntimeError("could not find a python to build zipapp")
        cmd = [str(Path(exe).parent / "pip"), "install", "pip>=19.3", "packaging>=20"]
        subprocess.check_call(cmd)
    yield exe
    if create_env_path is not None:
        shutil.rmtree(str(create_env_path))


@pytest.fixture(scope="session")
def zipapp(zipapp_build_env, tmp_path_factory):
    into = tmp_path_factory.mktemp("zipapp")
    path = Path(HERE).parent.parent / "tasks" / "make_zipapp.py"
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


@pytest.fixture()
def call_zipapp(zipapp, monkeypatch, tmp_path, zipapp_test_env, temp_app_data):
    def _run(*args):
        cmd = [str(zipapp_test_env), str(zipapp), "-vv", ensure_text(str(tmp_path / "env"))] + list(args)
        subprocess.check_call(cmd)

    return _run


@flaky(max_runs=2, min_passes=1)
def test_zipapp_help(call_zipapp, capsys):
    call_zipapp("-h")
    out, err = capsys.readouterr()
    assert not err


@pytest.mark.parametrize("seeder", ["app-data", "pip"])
def test_zipapp_create(call_zipapp, seeder):
    call_zipapp("--seeder", seeder)
