import os
import sys

import pytest
import scripttest


is_windows = (
    sys.platform.startswith("win") or
    (sys.platform == "cli" and os.name == "nt")
)
is_26 = sys.version_info[:2] == (2, 6)


@pytest.yield_fixture
def env(request):
    env = scripttest.TestFileEnvironment()
    try:
        yield env
    finally:
        env.clear()


def test_create_via_script(env):
    result = env.run('virtualenv', 'myenv')
    if is_windows:
        assert 'myenv\\Scripts\\activate.bat' in result.files_created
        assert 'myenv\\Scripts\\activate.ps1' in result.files_created
        assert 'myenv\\Scripts\\activate_this.py' in result.files_created
        assert 'myenv\\Scripts\\deactivate.bat' in result.files_created
        assert 'myenv\\Scripts\\pip.exe' in result.files_created
        assert 'myenv\\Scripts\\python.exe' in result.files_created
        assert 'myenv\\Scripts\\python2.exe' in result.files_created
    else:
        assert 'myenv/bin/activate.sh' in result.files_created
        assert 'myenv/bin/activate_this.py' in result.files_created
        assert 'myenv/bin/python' in result.files_created

def test_create_via_module(env):
    result = env.run('python', '-mvirtualenv.__main__' if is_26 else '-mvirtualenv', 'myenv')
    if is_windows:
        assert 'myenv\\Scripts\\activate.bat' in result.files_created
        assert 'myenv\\Scripts\\activate.ps1' in result.files_created
        assert 'myenv\\Scripts\\activate_this.py' in result.files_created
        assert 'myenv\\Scripts\\deactivate.bat' in result.files_created
        assert 'myenv\\Scripts\\pip.exe' in result.files_created
        assert 'myenv\\Scripts\\python.exe' in result.files_created
        assert 'myenv\\Scripts\\python2.exe' in result.files_created
    else:
        assert 'myenv/bin/activate.sh' in result.files_created
        assert 'myenv/bin/activate_this.py' in result.files_created
        assert 'myenv/bin/python' in result.files_created
