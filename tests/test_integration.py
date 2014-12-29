import pytest
import scripttest

@pytest.yield_fixture
def env(request):
    env = TestFileEnvironment()
    try:
        yield env
    finally:
        env.clear()


def test_create(env):
    env.run('virtualenv', 'myenv')
    assert env.files_created == {}

