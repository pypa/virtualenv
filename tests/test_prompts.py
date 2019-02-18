"""test that prompt behavior is correct in supported shells"""
from __future__ import absolute_import, unicode_literals

import os
import subprocess
import sys

import pytest

import virtualenv


ENV_DEFAULT = "env"
ENV_CUSTOM = "env_custom"

PREFIX_DEFAULT = "({}) ".format(ENV_DEFAULT)
PREFIX_CUSTOM = "!!!ENV!!!"

OUTPUT_FILE = "outfile"

VIRTUAL_ENV_DISABLE_PROMPT = "VIRTUAL_ENV_DISABLE_PROMPT"
VIRTUAL_ENV = "VIRTUAL_ENV"


@pytest.fixture(scope="module")
def tmp_root(tmp_path_factory):
    """Provide Path to root with default and custom venvs created."""
    root = tmp_path_factory.mktemp("env_root")
    virtualenv.create_environment(str(root / ENV_DEFAULT), no_setuptools=True, no_pip=True, no_wheel=True)
    virtualenv.create_environment(
        str(root / ENV_CUSTOM), prompt=PREFIX_CUSTOM, no_setuptools=True, no_pip=True, no_wheel=True
    )
    return root


@pytest.fixture(scope="function")
def clean_env():
    """Provide a fresh copy of the shell environment."""
    return os.environ.copy()


@pytest.mark.parametrize(["command", "code"], [("dir", 0), ("exit 1", 1)])
def test_exit_code(command, code, tmp_root):
    """Confirm subprocess.call exit codes work as expected at the unit test level."""
    assert subprocess.call(command, cwd=str(tmp_root), shell=True) == code


@pytest.mark.skipif(sys.platform.startswith("win"), reason="Invalid on Windows")
class TestBashPrompts:
    """Container for tests of bash prompt modifications."""

    @staticmethod
    def test_suppressed_prompt_default_env(tmp_root, clean_env):
        """Confirm VIRTUAL_ENV_DISABLE_PROMPT suppresses prompt changes on activate."""
        clean_env.update({VIRTUAL_ENV_DISABLE_PROMPT: "1"})
        command = 'echo "$PS1" > {1} && . {0}/bin/activate && echo "$PS1" >> {1}'.format(ENV_DEFAULT, OUTPUT_FILE)

        assert 0 == subprocess.call(command, cwd=str(tmp_root), shell=True, env=clean_env)

        lines = (tmp_root / OUTPUT_FILE).read_bytes().split(b"\n")
        assert lines[0] == lines[1]

    @staticmethod
    @pytest.mark.parametrize(["env", "prefix"], [(ENV_DEFAULT, PREFIX_DEFAULT), (ENV_CUSTOM, PREFIX_CUSTOM)])
    def test_activated_prompt(env, prefix, tmp_root):
        """Confirm prompt modification behavior with and without --prompt specified."""
        command = (
            'echo "$PS1" > {1} && . {0}/bin/activate && echo "$PS1" >> {1} ' '&& deactivate && echo "$PS1" >> {1}'
        ).format(env, OUTPUT_FILE)

        assert 0 == subprocess.call(command, cwd=str(tmp_root), shell=True)

        lines = (tmp_root / OUTPUT_FILE).read_bytes().split(b"\n")

        # Before activation and after deactivation
        assert lines[0] == lines[2]

        # Activated prompt
        assert lines[1] == prefix.encode("utf-8") + lines[0]
