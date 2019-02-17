"""test that prompt behavior is correct in supported shells"""
from __future__ import absolute_import, unicode_literals

import os
import subprocess
import sys
from collections import defaultdict
from pathlib import Path
from textwrap import dedent

import pytest

import virtualenv

ENV_DEFAULT = "env"
ENV_CUSTOM = "env_custom"

PREFIX_DEFAULT = "({}) ".format(ENV_DEFAULT)
PREFIX_CUSTOM = "---ENV---"

VIRTUAL_ENV_DISABLE_PROMPT = "VIRTUAL_ENV_DISABLE_PROMPT"
VIRTUAL_ENV = "VIRTUAL_ENV"

SHELL_LIST = ["bash", "fish", "csh", "xonsh", "cmd", "powershell"]


class EchoDict(dict):
    """Returns the value for the key if available, else returns the key."""

    def __getitem__(self, key):
        return self.get(key, key)


@pytest.fixture(scope="module")
def platform_check_skip(tmp_path_factory):
    """Return function triggering skip based on platform & shell."""
    platform_incompat = "No sane provision for {} on {} yet"

    def check(platform, shell):

        if (sys.platform.startswith("win") and shell in ["bash", "csh", "fish"]) or (
            sys.platform.startswith("linux") and shell in ["cmd", "powershell"]
        ):
            pytest.skip(platform_incompat.format(shell, platform))

        if sys.platform.startswith("win") and shell == "xonsh":
            pytest.skip("Provisioning xonsh on windows is unreliable")

        if shell == "xonsh" and sys.version_info < (3, 4):
            pytest.skip("xonsh requires Python 3.4 at least")

        if shell == "powershell":
            test_ps1 = tmp_path_factory.mktemp("posh_test") / "test.ps1"
            test_ps1.write_text("echo foo\n")

            if 0 != subprocess.call("powershell -File {}".format(str(test_ps1)), shell=True):
                pytest.skip("powershell script execution not enabled")
                # Enable with:  PS> Set-ExecutionPolicy -scope currentuser -ExecutionPolicy Bypass -Force;
                # Disable with: PS> Set-ExecutionPolicy -scope currentuser -ExecutionPolicy Restricted -Force;

    return check


@pytest.fixture(scope="module")
def custom_prompt_root(tmp_path_factory):
    """Provide Path to root with default and custom venvs created."""
    root = tmp_path_factory.mktemp("custom_prompt")
    virtualenv.create_environment(
        str(root / ENV_CUSTOM), prompt=PREFIX_CUSTOM, no_setuptools=True, no_pip=True, no_wheel=True
    )

    _, _, _, bin_dir = virtualenv.path_locations(str(root / ENV_DEFAULT))

    bin_dir_name = os.path.split(bin_dir)[-1]

    return root, bin_dir_name


@pytest.fixture(scope="module")
def clean_python_root(clean_python):
    root = Path(clean_python[0]).resolve().parent
    bin_dir_name = os.path.split(clean_python[1])[-1]

    return root, bin_dir_name


@pytest.fixture(scope="module")
def get_work_root(clean_python_root, custom_prompt_root):
    def pick_root(env):
        if env == ENV_DEFAULT:
            return clean_python_root
        elif env == ENV_CUSTOM:
            return custom_prompt_root
        else:
            raise ValueError("Invalid test environment")

    return pick_root


@pytest.fixture(scope="module")
def shell_info():
    class ShellInfo:

        execute_cmds = EchoDict({"cmd": "", "powershell": "powershell -File "})

        # {shell}.script.(normal|suppress).(default|custom)[extension]
        script_template = "{0}.script.{1}.{2}{3}"

        # {shell}.out.(normal|suppress).(default|custom)
        output_template = "{0}.out.{1}.{2}"

        testscript_extensions = defaultdict(lambda: "")
        testscript_extensions.update({"powershell": ".ps1", "cmd": ".bat"})

        preamble_cmds = {
            "bash": "",
            "fish": "",
            "csh": "set prompt=%",
            "xonsh": "$VIRTUAL_ENV = ''; $PROMPT = '{env_name}$ '",
            "cmd": "@echo off & set PROMPT=$P$G",
            "powershell": "",
        }

        prompt_cmds = {
            "bash": 'echo "$PS1"',
            "fish": "fish_prompt; echo ' '",
            "csh": r"set | grep -E 'prompt\s' | sed -E 's/^prompt\s+(.*)$/\1/'",
            "xonsh": "print(__xonsh__.shell.prompt)",
            "cmd": "echo %PROMPT%",
            "powershell": "prompt",
        }

        activate_cmds = defaultdict(lambda: "source ")
        activate_cmds.update({"powershell": ". ", "cmd": "call "})

        activate_scripts = {
            "bash": "activate",
            "fish": "activate.fish",
            "csh": "activate.csh",
            "xonsh": "activate.xsh",
            "cmd": "activate.bat",
            "powershell": "activate.ps1",
        }

        deactivate_cmds = defaultdict(lambda: "deactivate")
        deactivate_cmds.update({"cmd": "call deactivate"})

    return ShellInfo()


@pytest.fixture(scope="function")
def clean_env():
    """Provide a fresh copy of the shell environment."""
    return os.environ.copy()


@pytest.mark.parametrize("shell", SHELL_LIST)
@pytest.mark.parametrize("env", [ENV_DEFAULT, ENV_CUSTOM])
def test_suppressed_prompt(shell, env, get_work_root, clean_env, shell_info, platform_check_skip):
    """Confirm VIRTUAL_ENV_DISABLE_PROMPT suppresses prompt changes on activate."""
    platform_check_skip(sys.platform, shell)

    script_name = shell_info.script_template.format(shell, "suppress", env, shell_info.testscript_extensions[shell])
    output_name = shell_info.output_template.format(shell, "suppress", env)

    clean_env.update({VIRTUAL_ENV_DISABLE_PROMPT: "1"})

    work_root = get_work_root(env)

    # The extra "{prompt}" here copes with some oddity of xonsh in certain emulated terminal
    # contexts: xonsh can dump stuff into the first line of the recorded script output,
    # so we have to include a dummy line of output that can get munged w/o consequence.
    (work_root[0] / script_name).write_text(
        dedent(
            """\
        {preamble}
        {prompt}
        {prompt}
        {act_cmd}{env}/{bindir}/{act_script}
        {prompt}
    """.format(
                env=env,
                act_cmd=shell_info.activate_cmds[shell],
                preamble=shell_info.preamble_cmds[shell],
                prompt=shell_info.prompt_cmds[shell],
                act_script=shell_info.activate_scripts[shell],
                bindir=work_root[1],
            )
        )
    )

    command = "{} {} > {}".format(shell_info.execute_cmds[shell], script_name, output_name)

    assert 0 == subprocess.call(command, cwd=str(work_root[0]), shell=True, env=clean_env)

    lines = (work_root[0] / output_name).read_bytes().split(b"\n")

    # Is the prompt suppressed?
    assert lines[1] == lines[2], lines


@pytest.mark.parametrize("shell", SHELL_LIST)
@pytest.mark.parametrize(["env", "prefix"], [(ENV_DEFAULT, PREFIX_DEFAULT), (ENV_CUSTOM, PREFIX_CUSTOM)])
def test_activated_prompt(shell, env, prefix, get_work_root, shell_info, platform_check_skip):
    """Confirm prompt modification behavior with and without --prompt specified."""
    platform_check_skip(sys.platform, shell)

    script_name = shell_info.script_template.format(shell, "normal", env, shell_info.testscript_extensions[shell])
    output_name = shell_info.output_template.format(shell, "normal", env)

    work_root = get_work_root(env)

    # The extra "{prompt}" here copes with some oddity of xonsh in certain emulated terminal
    # contexts: xonsh can dump stuff into the first line of the recorded script output,
    # so we have to include a dummy line of output that can get munged w/o consequence.
    (work_root[0] / script_name).write_text(
        dedent(
            """\
        {preamble}
        {prompt}
        {prompt}
        {act_cmd}{env}/{bindir}/{act_script}
        {prompt}
        {deactivate}
        {prompt}
        """.format(
                env=env,
                act_cmd=shell_info.activate_cmds[shell],
                deactivate=shell_info.deactivate_cmds[shell],
                preamble=shell_info.preamble_cmds[shell],
                prompt=shell_info.prompt_cmds[shell],
                act_script=shell_info.activate_scripts[shell],
                bindir=work_root[1],
            )
        )
    )

    command = "{} {} > {}".format(shell_info.execute_cmds[shell], script_name, output_name)

    assert 0 == subprocess.call(command, cwd=str(work_root[0]), shell=True)

    lines = (work_root[0] / output_name).read_bytes().split(b"\n")

    # Before activation and after deactivation
    assert lines[1] == lines[3], lines

    # Activated prompt. This construction copes with messes like fish's ANSI codes for colorizing.
    # It's not as rigorous as I would like---it doesn't ensure no space is inserted between
    # a custom env prompt (argument to --prompt) and the base prompt---but it does provide assurance as
    # to the key pieces of content that should be present.
    before, env_marker, after = lines[2].partition(prefix.encode("utf-8"))
    assert env_marker != b"", lines

    # Separate handling for fish, which has color coding commands built into activate.fish that are
    # painful to work around
    if shell == "fish":
        # Looser assert
        assert lines[1] in after, lines
    else:
        # Stricter assert
        assert after == lines[1], lines
