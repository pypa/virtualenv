# coding: utf-8
import sys
import subprocess
import virtualenv
import pytest

VIRTUALENV_SCRIPT = virtualenv.__file__

def test_commandline_basic(tmpdir):
    """Simple command line usage should work"""
    subprocess.check_call([
        sys.executable,
        VIRTUALENV_SCRIPT,
        str(tmpdir.join('venv'))
    ])

def test_commandline_explicit_interp(tmpdir):
    """Specifying the Python interpreter should work"""
    subprocess.check_call([
        sys.executable,
        VIRTUALENV_SCRIPT,
        '-p', sys.executable,
        str(tmpdir.join('venv'))
    ])

# encodings on PyPy 3 is broken. See https://bitbucket.org/pypy/pypy/issues/2300
@pytest.mark.skipif("hasattr(sys, 'pypy_version_info') and sys.version_info[0] == 3")
def test_commandline_non_ascii_path(tmpdir):
    subprocess.check_call([
        sys.executable,
        VIRTUALENV_SCRIPT,
        '-p', sys.executable,
        str(tmpdir.join('venv中文'))
    ])

# The registry lookups to support the abbreviated "-p 3.5" form of specifying
# a Python interpreter on Windows don't seem to work with Python 3.5. The
# registry layout is not well documented, and it's not clear that the feature
# is sufficiently widely used to be worth fixing.
# See https://github.com/pypa/virtualenv/issues/864
@pytest.mark.skipif("sys.platform == 'win32' and sys.version_info[:2] >= (3,5)")
def test_commandline_abbrev_interp(tmpdir):
    """Specifying abbreviated forms of the Python interpreter should work"""
    if sys.platform == 'win32':
        fmt = '%s.%s'
    else:
        fmt = 'python%s.%s'
    abbrev = fmt % (sys.version_info[0], sys.version_info[1])
    subprocess.check_call([
        sys.executable,
        VIRTUALENV_SCRIPT,
        '-p', abbrev,
        str(tmpdir.join('venv'))
    ])

