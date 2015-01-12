import os
import sys
from itertools import product

import pytest
import scripttest


IS_WINDOWS = (
    sys.platform.startswith("win") or
    (sys.platform == "cli" and os.name == "nt")
)
IS_26 = sys.version_info[:2] == (2, 6)
IS_PYPY = hasattr(sys, 'pypy_version_info')


def locate_on_path(binary):
    paths = os.environ["PATH"].split(os.path.pathsep)
    for path in paths:
        binpath = os.path.join(path, binary)
        if os.path.exists(binpath):
            return binpath

PYTHON_BINS = set([
    "C:\\Python27\\python.exe",
    "C:\\Python27-x64\\python.exe",
    "C:\\Python33\\python.exe",
    "C:\\Python33-x64\\python.exe",
    "C:\\Python34\\python.exe",
    "C:\\Python34-x64\\python.exe",
    "C:\\PyPy\\pypy.exe",
    "C:\\PyPy3\\pypy.exe",
    None,
    "/usr/bin/python",
    "/usr/bin/python2.6",
    "/usr/bin/python2.7",
    "/usr/bin/python3.2",
    "/usr/bin/python3.3",
    "/usr/bin/python3.4",
    "/usr/bin/pypy",
    locate_on_path("python"),
    locate_on_path("python2.6"),
    locate_on_path("python2.7"),
    locate_on_path("python3.2"),
    locate_on_path("python3.3"),
    locate_on_path("python3.4"),
    locate_on_path("pypy"),
])


@pytest.yield_fixture
def env(request):
    env = scripttest.TestFileEnvironment()
    try:
        yield env
    finally:
        env.clear()


@pytest.yield_fixture(params=PYTHON_BINS)
def python(request):
    if request.param is None or os.path.exists(request.param):
        yield request.param
    else:
        pytest.skip(msg="Implementation at %r not available." % request.param)


@pytest.mark.parametrize("systemsitepackages,viascript", product([False, True], repeat=2))
def test_create(env, python, systemsitepackages, viascript):
    if viascript:
        args = ["python", "-mvirtualenv.__main__" if IS_26 else "-mvirtualenv"]
    else:
        args = ["virtualenv"]

    args += ["--verbose", "myenv"]
    if systemsitepackages:
        args += ["--system-site-packages"]
    if python:
        args += ["--python", python]
    result = assert_no_strays(env.run(*args))  # new env
    print(result)
    assert_env_is_created(env, python, result)
    print("********* RECREATE *********")
    result = assert_no_strays(env.run(*args))  # recreate it
    print(result)
    assert_env_is_working(env, python, result)  # on recreated env


def test_create_from_tox(env):
    result = env.run(
        'tox', '-c', os.path.join(os.path.dirname(__file__), 'test_tox.ini'),
        '--skip-missing-interpreters'
    )
    print(result)


def assert_no_strays(result):
    for name in result.files_created:
        assert name.startswith("myenv")
    return result


def assert_env_is_created(env, python, result):
    if IS_WINDOWS:
        if not python and IS_PYPY or python and "pypy" in python:
            assert 'myenv\\bin\\activate.bat' in result.files_created
            assert 'myenv\\bin\\activate.ps1' in result.files_created
            assert 'myenv\\bin\\activate_this.py' in result.files_created
            assert 'myenv\\bin\\deactivate.bat' in result.files_created
            assert 'myenv\\bin\\pip.exe' in result.files_created
            assert 'myenv\\bin\\python.exe' in result.files_created
        else:
            assert 'myenv\\Scripts\\activate.bat' in result.files_created
            assert 'myenv\\Scripts\\activate.ps1' in result.files_created
            assert 'myenv\\Scripts\\activate_this.py' in result.files_created
            assert 'myenv\\Scripts\\deactivate.bat' in result.files_created
            assert 'myenv\\Scripts\\pip.exe' in result.files_created
            assert 'myenv\\Scripts\\python.exe' in result.files_created
    else:
        assert 'myenv/bin/activate.sh' in result.files_created
        assert 'myenv/bin/activate_this.py' in result.files_created
        assert 'myenv/bin/python' in result.files_created
        assert "myenv/bin/pip" in result.files_created

    if IS_WINDOWS:
        if not python and IS_PYPY or python and "pypy" in python:
            result = assert_no_strays(env.run('myenv\\bin\\pip', 'install', 'nameless'))
            print(result)
            assert "myenv\\bin\\nameless.exe" in result.files_created
        else:
            result = assert_no_strays(env.run('myenv\\Scripts\\pip install nameless'))
            print(result)
            assert "myenv\\Scripts\\nameless.exe" in result.files_created
    else:
        result = assert_no_strays(env.run('myenv/bin/pip install nameless'))
        print(result)
        assert "myenv/bin/nameless" in result.files_created
    assert_env_is_working(env, python, result)


def assert_env_is_working(env, python, result):
    if IS_WINDOWS:
        if not python and IS_PYPY or python and "pypy" in python:
            env.run('myenv\\bin\\python', '-c', 'import nameless')
            env.run('myenv\\bin\\nameless')
        else:
            env.run('myenv\\Scripts\\python', '-c', 'import nameless')
            env.run('myenv\\Scripts\\nameless')
    else:
        env.run('myenv/bin/python', '-c', 'import nameless')
        env.run('myenv/bin/nameless')

# TODO: Test if source packages with C extensions can be built or installed
