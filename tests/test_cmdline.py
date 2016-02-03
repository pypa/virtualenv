import sys
import subprocess
import virtualenv

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

def test_commandline_abbrev_interp(tmpdir):
    """Specifying abbreviated forms of the Python interpreter should work"""
    if sys.platform == 'win32':
        fmt = 'py%s%s'
    else:
        fmt = 'python%s.%s'
    abbrev = fmt % (sys.version_info[0], sys.version_info[1])
    subprocess.check_call([
        sys.executable,
        VIRTUALENV_SCRIPT,
        '-p', abbrev,
        str(tmpdir.join('venv'))
    ])

