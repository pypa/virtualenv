import os
import sys
from itertools import chain
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


class TestVirtualEnvironment(scripttest.TestFileEnvironment):
    def __init__(self, base_path, target_python, creation_args, virtualenv_name="myenv"):
        self.creation_args = creation_args
        self.virtualenv_name = virtualenv_name
        self.target_python = target_python
        self.is_pypy = not target_python and IS_PYPY or target_python and "pypy" in target_python
        super(TestVirtualEnvironment, self).__init__(base_path)

    def __str__(self):
        return '_'.join(self.creation_args)

    @property
    def has_systemsitepackages(self):
        return '--system-site-packages' in self.creation_args

    def binpath(self, *args):
        if self.is_pypy or not IS_WINDOWS:
            return os.path.join(self.virtualenv_name, 'bin', *args)
        else:
            return os.path.join(self.virtualenv_name, 'Scripts', *args)

    def exepath(self, *args):
        if IS_WINDOWS:
            if self.is_pypy:
                return os.path.join(self.virtualenv_name, 'bin', *args) + '.exe'
            else:
                return os.path.join(self.virtualenv_name, 'Scripts', *args) + '.exe'
        else:
            return os.path.join(self.virtualenv_name, 'bin', *args)

    def run(self, *args):
        print("******************** RUNNING: %s ********************" % ' '.join(args))
        result = super(TestVirtualEnvironment, self).run(*args)
        print(result)
        return result

    def run_inside(self, binary, *args):
        return self.run(self.binpath(binary), *args)

    def create_virtualenv(self):
        args = list(self.creation_args)
        if self.target_python:
            args += ["--python", self.target_python]
        args += ["--verbose", self.virtualenv_name]
        result = self.run(*args)
        for name in result.files_created:
            assert name.startswith(self.virtualenv_name)
        return result

    def has_package(self, package):
        if self.target_python:
            result = self.run(
                self.target_python, "-c", "import " + package,
                expect_error=True,
                expect_stderr=True
            )
            print("*************** has_package(%r) ***************" % package)
            print(result)
            print("********************* %s **********************" % result.returncode)
            return result.returncode == 0


@pytest.yield_fixture(params=PYTHON_BINS)
def python(request):
    if request.param is None or os.path.exists(request.param):
        yield request.param
    else:
        pytest.skip(msg="Implementation at %r not available." % request.param)


def assert_env_creation(env):
    result = env.create_virtualenv()

    if IS_WINDOWS:
        if env.is_pypy:
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


########################################################################################################################
# The actual tests
########################################################################################################################

@pytest.mark.parametrize("options", [
    '_'.join(chain.from_iterable(i))
    for i in product(
        [["python", "-mvirtualenv"], ["virtualenv"]],
        [['--system-site-packages'], []]
    )
])
def test_recreate(python, options, tmpdir):
    env = TestVirtualEnvironment(str(tmpdir.join('sandbox')), python, options.split('_'))

    assert_env_creation(env)

    if env.has_systemsitepackages and env.has_package('nameless'):
        env.run_inside('python', '-c', 'import nameless')

    result = env.run_inside('pip', 'install', 'nameless')

    if env.has_systemsitepackages:
        assert env.exepath('nameless') not in result.files_created
        result = env.run_inside('pip', 'install', '--ignore-installed', 'nameless')

    assert env.exepath('nameless') in result.files_created
    env.run_inside('python', '-c', 'import nameless')
    env.run_inside('nameless')

    print("********* RECREATE *********")

    result = env.create_virtualenv()

    env.run_inside('python', '-c', 'import nameless')
    env.run_inside('nameless')


@pytest.mark.skipif(IS_26, reason="Tox doesn't work on Python 2.6")
def test_create_from_tox(tmpdir):
    env = scripttest.TestFileEnvironment(str(tmpdir.join('sandbox')))
    result = env.run(
        'tox', '-c', os.path.join(os.path.dirname(__file__), 'test_tox.ini'),
        '--skip-missing-interpreters'
    )
    print(result)


# TODO: Test if source packages with C extensions can be built or installed
