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


def resolve_path(path):
    """
    Expands ~ in the path and resolves any symlinks.
    """
    if path is not None:
        path = os.path.realpath(os.path.expanduser(path))
    return path


PYTHON_BINS = [
    # The values in the tuples:
    #   is global, bin path, site-package path
    #
    # Details:
    # - is global: If set to False then tests with `--system-site-packages` are disabled as we can't statically infer
    #              here how a virtualenv with `--system-site-packages` will behave
    # - bin path: Absolute path to the pythonbin
    # - site-package path: expected location of site-packages. Used for `test_sitepackages`.
    (True, "C:\\Python27\\python.exe", "lib\\site-packages"),
    (True, "C:\\Python27-x64\\python.exe", "lib\\site-packages"),
    (True, "C:\\Python33\\python.exe", "lib\\site-packages"),
    (True, "C:\\Python33-x64\\python.exe", "lib\\site-packages"),
    (True, "C:\\Python34\\python.exe", "lib\\site-packages"),
    (True, "C:\\Python34-x64\\python.exe", "lib\\site-packages"),
    (True, "C:\\PyPy\\pypy.exe", "site-packages"),
    (True, "C:\\PyPy3\\pypy.exe", "site-packages"),
    (False, None, None),
    (True, resolve_path("~/.pyenv/shims/python"), None),
    (True, resolve_path("~/.pyenv/shims/python2.6"), "lib/python2.6/site-packages"),
    (True, resolve_path("~/.pyenv/shims/python2.7"), "lib/python2.7/site-packages"),
    (True, resolve_path("~/.pyenv/shims/python3.2"), "lib/python3.2/site-packages"),
    (True, resolve_path("~/.pyenv/shims/python3.3"), "lib/python3.3/site-packages"),
    (True, resolve_path("~/.pyenv/shims/python3.4"), "lib/python3.4/site-packages"),
    (True, resolve_path("~/.pyenv/shims/pypy"), "site-packages"),
]
if not os.environ.get("CIRCLE_BUILD_NUM"):
    # CircleCI messed these up badly ... they use pyenv
    PYTHON_BINS += [
        (True, "/usr/bin/python", None),
        (True, "/usr/bin/python2.6", "lib/python2.6/site-packages"),
        (True, "/usr/bin/python2.7", "lib/python2.7/site-packages"),
        (True, "/usr/bin/python3.2", "lib/python3.2/site-packages"),
        (True, "/usr/bin/python3.3", "lib/python3.3/site-packages"),
        (True, "/usr/bin/python3.4", "lib/python3.4/site-packages"),
        (True, "/usr/bin/pypy", "site-packages"),
    ]

for path, sitepackages in [
    (locate_on_path("python"), None),
    (locate_on_path("python2.6"), None),
    (locate_on_path("python2.7"), None),
    (locate_on_path("python3.2"), None),
    (locate_on_path("python3.3"), None),
    (locate_on_path("python3.4"), None),
    (locate_on_path("pypy"), None),
]:
    # I'm terrible here but I want certain checks disabled for these paths: the --system-site-packages checks, otherwise
    # I have to reimplement bin resolving here, and it's a bad idea to duplicate logic in tests.
    if (True, path, sitepackages) not in PYTHON_BINS:
        if path:
            PYTHON_BINS.append((False, path, sitepackages))

PYTHON_BINS = [
    (is_global, path, sitepackages)
    for is_global, path, sitepackages in PYTHON_BINS
    if path is None or os.path.exists(path)
]

OPTIONS = [
    list(chain.from_iterable(i))
    for i in product(
        [["virtualenv"], ["python", "-mvirtualenv.__main__" if IS_26 else "-mvirtualenv"]],
        [['--system-site-packages'], []]
    )
]


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
            return os.path.join(self.base_path, self.virtualenv_name, 'bin', *args)
        else:
            return os.path.join(self.base_path, self.virtualenv_name, 'Scripts', *args)

    def exepath(self, *args):
        if IS_WINDOWS:
            if self.is_pypy:
                return os.path.join(self.virtualenv_name, 'bin', *args) + '.exe'
            else:
                return os.path.join(self.virtualenv_name, 'Scripts', *args) + '.exe'
        else:
            return os.path.join(self.virtualenv_name, 'bin', *args)

    def run(self, *args, **kwargs):
        print("******************** RUNNING: %s ********************" % ' '.join(args))
        result = super(TestVirtualEnvironment, self).run(*args, expect_stderr=True, **kwargs)
        print(result)
        return result

    def run_inside(self, binary, *args, **kwargs):
        return self.run(self.binpath(binary), *args, **kwargs)

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
        print("*************** has_package(%r):" % package)
        if self.target_python:
            result = self.run(
                self.target_python, "-c", "import {0}; print({0}.__file__)".format(package),
                expect_error=True
            )
            print("             => %s" % result.returncode)
            return result.returncode == 0
        print("             => None")


@pytest.fixture(
    params=PYTHON_BINS,
    ids=["-python=%s" % (i or "<CURRENT>") for _, i, _ in PYTHON_BINS],
    scope="session",
)
def python_conf(request):
    is_global, path, sitepackages = request.param
    if path is None or os.path.exists(path):
        return is_global, path, sitepackages
    else:
        pytest.skip(msg="Implementation at %r not available." % path)


@pytest.yield_fixture(
    params=OPTIONS,
    ids=[" ".join(opt) + " " for opt in OPTIONS],
    scope="session",
)
def env(request, python_conf):
    # This exists as a fixture to enable session-scoped virtualenvs
    # (or in other words, reuse virtualenvs for tests => faster tests)
    try:
        tmpdir = request.config._tmpdirhandler.mktemp('env', numbered=True)

        env = TestVirtualEnvironment(str(tmpdir.join('sandbox')), python_conf[1], request.param)
        assert_env_creation(env)
        yield env
    finally:
        tmpdir.remove(ignore_errors=True)


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


def test_create_2time(env):
    print("********* RECREATE *********")
    # Test to see if recreation doesn't blow up something
    env.create_virtualenv()


def test_installation(env, python_conf):
    is_global, _, _ = python_conf
    package_available_outside = env.has_systemsitepackages and env.has_package('nameless')

    if is_global:
        # If is_global then were sure that the target is not in a virtualenv. We can reliably expect certain behavior
        # when an package is installed globally and --system-site-packages is specifed
        if package_available_outside:
            # We can expect to be importable
            env.run_inside('python', '-c', 'import nameless')

        result = env.run_inside('pip', 'install', 'nameless')

        if package_available_outside:
            # And we can expect that pip doesn't do anything - it's already installed outside.
            assert env.exepath('nameless') not in result.files_created

            # If so, then we force install it, just to check that the bin is working
            result = env.run_inside('pip', 'install', '--ignore-installed', 'nameless')

        # Have we got the bin created?
        assert env.exepath('nameless') in result.files_created
        env.run_inside('python', '-c', 'import nameless')
        # And is the bin working?
        env.run_inside('nameless')
    else:
        # This target interpreter is prolly inside a virtualenv (eg, these tests were run inside a virtualenv),
        # therefore we grossly simplify the assertions to just check that it's importable
        env.run_inside('pip', 'install', 'nameless')
        env.run_inside('python', '-c', 'import nameless')

    # Now downgrade the package. This should always install it in the virtualenv.
    env.run_inside('pip', 'install', '--ignore-installed', 'nameless==0.1.2')
    # Now we test that the package is imported from the virtualenv (and not global whatever)
    env.run_inside('python', '-c',
                   'import nameless; assert nameless.__version__ == "0.1.2", '
                   '"Version is not 0.1.2: %r. __file__=%r" % (nameless.__version__, nameless.__file__)')


@pytest.mark.skipif(IS_26, reason="Tox doesn't work on Python 2.6")
def test_create_w_tox(tmpdir):
    env = scripttest.TestFileEnvironment(str(tmpdir.join('sandbox')), capture_temp=True)
    result = env.run(
        'tox', '-c', os.path.join(os.path.dirname(__file__), 'test_tox.ini'),
        '--skip-missing-interpreters'
    )
    print(result)


def test_sitepackages(env, python_conf):
    _, python, sitepackages = python_conf
    if sitepackages is None:
        pytest.skip(msg="No site-packages specified for this configuration.")
    sitepackages_path = os.path.join(
        env.base_path, env.virtualenv_name, sitepackages
    )
    env.run_inside("python", "-c", "import sys; assert {0!r} in sys.path, 'is not in %r' % sys.path".format(
        sitepackages_path
    ))
    with open(os.path.join(sitepackages_path, "mymodule.pth"), 'w') as fh:
        fh.write(os.path.join(os.path.dirname(__file__), "testsite"))
    env.run_inside("python", "-c", "import mymodule")


def test_pip_inst_ext(env):
    if IS_WINDOWS and env.target_python:
        pytest.skip(msg="Disabled on windows. Compiler needs different environment.")
    base_dir = os.path.join(os.path.dirname(__file__), 'testcext')
    env.run_inside('pip', 'install', os.path.join(base_dir, 'test-cext-1.0.zip'))
    env.run_inside('python', '-c', 'import test_cext')


def test_reg_inst_ext(env):
    if IS_WINDOWS and env.target_python:
        pytest.skip(msg="Disabled on windows. Compiler needs different environment.")
    base_dir = os.path.join(os.path.dirname(__file__), 'testcext')
    env.run_inside('python', 'setup.py', 'install', cwd=base_dir)
    env.run_inside('python', '-c', 'import test_cext')
