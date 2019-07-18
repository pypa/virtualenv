from __future__ import unicode_literals

import json
import os.path
import subprocess
import sys

import pytest

import virtualenv

HERE = os.path.dirname(os.path.dirname(__file__))


def _python(v):
    return virtualenv.get_installed_pythons().get(v, "python{}".format(v))


@pytest.fixture(scope="session")
def call_zipapp(tmp_path_factory):
    if sys.version_info[:2] == (3, 4):
        pytest.skip("zipapp was introduced in python3.5")
    pyz = str(tmp_path_factory.mktemp(basename="zipapp") / "virtualenv.pyz")
    subprocess.check_call(
        (_python("3"), os.path.join(HERE, "tasks/make_zipapp.py"), "--root", virtualenv.HERE, "--dest", pyz)
    )

    def zipapp_make_env(path, python=None):
        cmd = (sys.executable, pyz, "--no-download", path)
        if python:
            cmd += ("-p", python)
        subprocess.check_call(cmd)

    return zipapp_make_env


@pytest.fixture(scope="session")
def call_wheel(tmp_path_factory):
    wheels = tmp_path_factory.mktemp(basename="wheel")
    subprocess.check_call((sys.executable, "-m", "pip", "wheel", "--no-deps", "-w", str(wheels), HERE))
    wheel, = wheels.iterdir()

    def wheel_make_env(path, python=None):
        cmd = (sys.executable, "-m", "virtualenv", "--no-download", path)
        if python:
            cmd += ("-p", python)
        env = dict(os.environ, PYTHONPATH=str(wheel))
        subprocess.check_call(cmd, env=env)

    return wheel_make_env


def test_zipapp_basic_invocation(call_zipapp, tmp_path):
    _test_basic_invocation(call_zipapp, tmp_path)


def test_wheel_basic_invocation(call_wheel, tmp_path):
    _test_basic_invocation(call_wheel, tmp_path)


def _test_basic_invocation(make_env, tmp_path):
    venv = tmp_path / "venv"
    make_env(str(venv))
    assert_venv_looks_good(
        venv, list(sys.version_info), "{}{}".format(virtualenv.EXPECTED_EXE, ".exe" if virtualenv.IS_WIN else "")
    )


def version_exe(venv, exe_name):
    _, _, _, bin_dir = virtualenv.path_locations(str(venv))
    exe = os.path.join(bin_dir, exe_name)
    script = "import sys; import json; print(json.dumps(dict(v=list(sys.version_info), e=sys.executable)))"
    cmd = [exe, "-c", script]
    out = json.loads(subprocess.check_output(cmd, universal_newlines=True))
    return out["v"], out["e"]


def assert_venv_looks_good(venv, version_info, exe_name):
    assert venv.exists()
    version, exe = version_exe(venv, exe_name=exe_name)
    assert version[: len(version_info)] == version_info
    assert exe != sys.executable


def _test_invocation_dash_p(make_env, tmp_path):
    venv = tmp_path / "venv"
    python = {2: _python("3"), 3: _python("2.7")}[sys.version_info[0]]
    make_env(str(venv), python)
    expected = {3: 2, 2: 3}[sys.version_info[0]]
    assert_venv_looks_good(venv, [expected], "python{}".format(".exe" if virtualenv.IS_WIN else ""))


def test_zipapp_invocation_dash_p(call_zipapp, tmp_path):
    _test_invocation_dash_p(call_zipapp, tmp_path)


def test_wheel_invocation_dash_p(call_wheel, tmp_path):
    _test_invocation_dash_p(call_wheel, tmp_path)
