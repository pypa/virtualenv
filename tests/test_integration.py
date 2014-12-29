import pytest
import scripttest

@pytest.yield_fixture
def env(request):
    env = scripttest.TestFileEnvironment()
    try:
        yield env
    finally:
        env.clear()


def test_create_via_script(env):
    env.run('virtualenv', 'myenv')
    assert env.files_created == {}


def test_create_via_module(env):
    env.run('python', '-mvirtualenv', 'myenv')
    assert env.files_created == {}
