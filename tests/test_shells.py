import sys
import subprocess
import virtualenv
import pytest
import tempfile
import shutil

VIRTUALENV_SCRIPT = virtualenv.__file__

#
# def test_commandline_basic(tmpdir):
#     """Simple command line usage should work"""
#     subprocess.check_call([
#         sys.executable,
#         VIRTUALENV_SCRIPT,
#         str(tmpdir.join('venv'))
#     ])


@pytest.fixture(scope="module")
def tmpenv():
    tmpenv = tempfile.mkdtemp()

    subprocess.check_call([
        sys.executable, VIRTUALENV_SCRIPT, tmpenv
    ])

    yield tmpenv
    shutil.rmtree(tmpenv)


#@pytest.mark.skipif("sys.platform == 'win32'")
def test_bash_activate(tmpenv):
    # if sys.platform == 'win32':
    #     fmt = '%s.%s'
    # else:
    #     fmt = 'python%s.%s'
    # abbrev = fmt % (sys.version_info[0], sys.version_info[1])
    subprocess.check_call([
        'bash', '-c', 'source %s/bin/activate' % tmpenv
    ])


#@pytest.mark.skipif("sys.platform == 'win32'")
def test_fish_activate(tmpenv):
    subprocess.check_call([
        'fish', '-c', 'source %s/bin/activate.fish' % tmpenv
    ])


#@pytest.mark.skipif("sys.platform == 'win32'")
def test_csh_activate(tmpenv):
    subprocess.check_call([
        'csh', '-c', 'source %s/bin/activate.csh' % tmpenv
    ])

#@pytest.mark.skipif("sys.platform == 'win32'")
def test_powershell_activate(tmpenv):
    subprocess.check_call([
        'powershell', '-Command', '". %s/bin/activate.ps1"' % tmpenv
    ])
