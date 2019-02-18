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


def fix_PS1_return(result, trim_newline=True):
    """Replace select byte values with escape sequences."""
    result = result.replace(b"\x1b", b"\\e")
    result = result.replace(b"\x07", b"\\a")

    if trim_newline and result[-1:] == b"\n":
        return result[:-1]
    else:
        return result


@pytest.mark.parametrize(["command", "code"], [("dir", 0), ("exit 1", 1)])
def test_exit_code(command, code, tmp_root):
    assert subprocess.call(command, cwd=str(tmp_root), shell=True) == code


@pytest.mark.skipif(sys.platform.startswith("win"), reason="Invalid on Windows")
class TestBashPrompts:
    @staticmethod
    @pytest.fixture(scope="class")
    def PS1():
        return os.environ.get("PS1")

    @staticmethod
    def test_suppressed_prompt_default_env_output(tmp_root, PS1, clean_env):
        """Check correct form of PS1 via subprocess.check_output().

        Duplicates test_suppressed_prompt_default_env_file, but demonstrates
        how to go about handling a test like this without using a temporary
        file, in case that's useful later.

        """
        clean_env.update({VIRTUAL_ENV_DISABLE_PROMPT: "1"})
        command = '. {0}/bin/activate && echo "$PS1"'.format(ENV_DEFAULT)
        result = subprocess.check_output(command, cwd=str(tmp_root), shell=True, env=clean_env)
        result = fix_PS1_return(result)

        # This assert MUST be made by encoding PS1, **NOT** by decoding
        # result. Python's decoding machinery mangles the content of the
        # returned $PS1 ~irretrievably.
        assert result == PS1.encode()

    @staticmethod
    def test_suppressed_prompt_default_env_file(tmp_root, clean_env):
        clean_env.update({VIRTUAL_ENV_DISABLE_PROMPT: "1"})
        command = 'echo "$PS1" > {1} && . {0}/bin/activate && echo "$PS1" >> {1}'.format(ENV_DEFAULT, OUTPUT_FILE)

        assert 0 == subprocess.call(command, cwd=str(tmp_root), shell=True, env=clean_env)

        lines = (tmp_root / OUTPUT_FILE).read_bytes().split(b"\n")
        assert lines[0] == lines[1]

    @staticmethod
    @pytest.mark.parametrize(["env", "prefix"], [(ENV_DEFAULT, PREFIX_DEFAULT), (ENV_CUSTOM, PREFIX_CUSTOM)])
    def test_activated_prompt(env, prefix, tmp_root):
        command = (
            'echo "$PS1" > {1} && . {0}/bin/activate && echo "$PS1" >> {1} ' '&& deactivate && echo "$PS1" >> {1}'
        ).format(env, OUTPUT_FILE)

        assert 0 == subprocess.call(command, cwd=str(tmp_root), shell=True)

        lines = (tmp_root / OUTPUT_FILE).read_bytes().split(b"\n")

        # Before activation and after deactivation
        assert lines[0] == lines[2]

        # Activated prompt
        assert lines[1] == prefix.encode("utf-8") + lines[0]
