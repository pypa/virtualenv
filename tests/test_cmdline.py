import os
import subprocess
import sys

import pytest

import virtualenv


def get_src(path):
    base, _ = os.path.splitext(path)
    if virtualenv.is_jython and base.endswith("$py"):
        base = base[:-3]  # strip away Jython ext
    return "{}.py".format(base)


VIRTUALENV_SCRIPT = get_src(virtualenv.__file__)


def test_commandline_basic(tmpdir):
    """Simple command line usage should work"""
    subprocess.check_output([sys.executable, VIRTUALENV_SCRIPT, str(tmpdir.join("venv"))], stderr=subprocess.STDOUT)


def test_commandline_explicit_interp(tmpdir):
    """Specifying the Python interpreter should work"""
    subprocess.check_call([sys.executable, VIRTUALENV_SCRIPT, "-p", sys.executable, str(tmpdir.join("venv"))])


# The registry lookups to support the abbreviated "-p 3.5" form of specifying
# a Python interpreter on Windows don't seem to work with Python 3.5. The
# registry layout is not well documented, and it's not clear that the feature
# is sufficiently widely used to be worth fixing.
# See https://github.com/pypa/virtualenv/issues/864
@pytest.mark.skipif("sys.platform == 'win32' and sys.version_info[:1] >= (3,)")
def test_commandline_abbrev_interp(tmpdir):
    """Specifying abbreviated forms of the Python interpreter should work"""
    abbrev = "{}{}.{}".format("" if sys.platform == "win32" else "python", *sys.version_info[0:2])
    subprocess.check_call([sys.executable, VIRTUALENV_SCRIPT, "-p", abbrev, str(tmpdir.join("venv"))])
