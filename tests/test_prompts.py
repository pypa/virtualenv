"""test that prompt behavior is correct in supported shells"""
from __future__ import absolute_import, unicode_literals

import subprocess

import pytest

import virtualenv

try:
    from pathlib import Path
except ImportError:
    from pathlib2 import Path

CUSTOM_PROMPT = "!!!ENV!!!"
ENV_DEFAULT = "env"
ENV_CUSTOM = "env_custom"


@pytest.fixture(scope="module")
def env_root(tmp_path_factory):
    """Provide Path to root with default and custom venvs created."""
    root = tmp_path_factory.mktemp("env_root")
    virtualenv.create_environment(
        str(root / ENV_DEFAULT),
        no_setuptools=True,
        no_pip=True,
        no_wheel=True,
    )
    virtualenv.create_environment(
        str(root / ENV_CUSTOM),
        prompt=CUSTOM_PROMPT,
        no_setuptools=True,
        no_pip=True,
        no_wheel=True,
    )
    return root


def test_functional_env_root(env_root):
    assert subprocess.call(
        'ls',
        cwd=str(env_root),
        shell=True,
    ) == 0


def test_nonzero_exit(env_root):
    assert subprocess.call(
        'exit 1',
        cwd=str(env_root),
        shell=True,
    ) == 1


class TestBashPrompts:

    @staticmethod
    def test_dummy(env_root):
        assert 1 == 1
