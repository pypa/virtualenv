import os.path
import subprocess
import sys

import pytest

import virtualenv

HERE = os.path.dirname(os.path.dirname(__file__))


def _python(v):
    return virtualenv.get_installed_pythons().get(v, "python{}".format(v))


def _major_version(venv):
    _, _, _, bin_dir = virtualenv.path_locations(venv)
    exe = os.path.join(bin_dir, "python")
    cmd = (exe, "-c", "import sys; print(sys.version_info[0])")
    out = subprocess.check_output(cmd)
    return int(out)


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
    subprocess.check_call((sys.executable, "-mpip", "wheel", "--no-deps", "-w", str(wheels), HERE))
    wheel, = wheels.iterdir()

    def wheel_make_env(path, python=None):
        cmd = (sys.executable, "-mvirtualenv", "--no-download", path)
        if python:
            cmd += ("-p", python)
        env = dict(os.environ, PYTHONPATH=str(wheel))
        subprocess.check_call(cmd, env=env)

    return wheel_make_env


def _test_basic_invocation(make_env, tmp_path):
    venv = tmp_path / "venv"
    make_env(str(venv))
    assert venv.exists()
    assert _major_version(str(venv)) == sys.version_info[0]


def test_zipapp_basic_invocation(call_zipapp, tmp_path):
    _test_basic_invocation(call_zipapp, tmp_path)


def test_wheel_basic_invocation(call_wheel, tmp_path):
    _test_basic_invocation(call_wheel, tmp_path)


def _test_invocation_dash_p(make_env, tmp_path):
    venv = tmp_path / "venv"
    python = {2: _python("3"), 3: _python("2.7")}[sys.version_info[0]]
    make_env(str(venv), python)
    assert venv.exists()
    expected = {3: 2, 2: 3}[sys.version_info[0]]
    assert _major_version(str(venv)) == expected


def test_zipapp_invocation_dash_p(call_zipapp, tmp_path):
    _test_invocation_dash_p(call_zipapp, tmp_path)


def test_wheel_invocation_dash_p(call_wheel, tmp_path):
    _test_invocation_dash_p(call_wheel, tmp_path)
