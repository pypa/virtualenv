"""test that prompt behavior is correct in supported shells"""
from __future__ import absolute_import, unicode_literals

import os
import subprocess
import sys
from collections import namedtuple
from textwrap import dedent

import pytest

import virtualenv
from virtualenv import IS_DARWIN, IS_WIN

try:
    from pathlib import Path
except ImportError:
    from pathlib2 import Path

VIRTUAL_ENV_DISABLE_PROMPT = "VIRTUAL_ENV_DISABLE_PROMPT"

# This must match the DEST_DIR provided in the ../conftest.py:clean_python fixture
ENV_DEFAULT = "env"

# This can be anything
ENV_CUSTOM = "env_custom"

# Standard prefix, surround the env name in parentheses and separate by a space
PREFIX_DEFAULT = "({}) ".format(ENV_DEFAULT)

# Arbitrary prefix for the environment that's provided a 'prompt' arg
PREFIX_CUSTOM = "---ENV---"

# Temp script filename template: {shell}.script.(normal|suppress).(default|custom)[extension]
SCRIPT_TEMPLATE = "{}.script.{}.{}{}"

# Temp output filename template: {shell}.out.(normal|suppress).(default|custom)
OUTPUT_TEMPLATE = "{}.out.{}.{}"

SHELL_LIST = ["bash", "fish", "csh", "xonsh", "cmd", "powershell"]


# Py2 doesn't like unicode in the environment
def env_compat(string):
    return string.encode("utf-8") if sys.version_info.major < 3 else string


@pytest.fixture(scope="module")
def posh_execute_enabled(tmp_path_factory):
    if not IS_WIN:
        return False

    test_ps1 = tmp_path_factory.mktemp("posh_test") / "test.ps1"
    with open(str(test_ps1), "w") as f:
        f.write("echo foo\n")

    return 0 == subprocess.call("powershell -File {}".format(str(test_ps1)), shell=True)


@pytest.fixture(scope="module")
def platform_check_skip(posh_execute_enabled, pytestconfig):
    """Check whether to skip based on platform & shell.

    Returns a string if test should be skipped, or None if test should proceed.

    """
    platform_incompat = "No sane provision for {} on {} yet"

    def check(platform, shell):

        if shell == "bash":
            if IS_WIN:
                return platform_incompat.format(shell, platform)
        elif shell == "csh":
            if IS_WIN:
                return platform_incompat.format(shell, platform)
        elif shell == "fish":
            if IS_WIN:
                return platform_incompat.format(shell, platform)
        elif shell == "cmd":
            if not IS_WIN:
                return platform_incompat.format(shell, platform)
        elif shell == "powershell":
            if not IS_WIN:
                return platform_incompat.format(shell, platform)

            if not posh_execute_enabled:
                return "powershell script execution fails; is it enabled?"
                # Enable with:  PS> Set-ExecutionPolicy -scope currentuser -ExecutionPolicy Bypass -Force;
                # Disable with: PS> Set-ExecutionPolicy -scope currentuser -ExecutionPolicy Restricted -Force;

        elif shell == "xonsh":
            if IS_WIN:
                return "Provisioning xonsh on windows is unreliable"

            if sys.version_info < (3, 4):
                return "xonsh requires Python 3.4 at least"

            if not pytestconfig.getoption("--xonsh-prompt"):
                return "'--xonsh-prompt' command line option not specified"

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
    ShellInfo = namedtuple(
        "ShellInfo",
        [
            "execute_cmd",
            "prompt_cmd",
            "activate_script",
            "testscript_extension",
            "preamble_cmd",
            "activate_cmd",
            "deactivate_cmd",
        ],
    )

    return {
        "bash": ShellInfo(
            execute_cmd="bash",
            prompt_cmd='echo "$PS1"',
            activate_script="activate",
            testscript_extension="",
            preamble_cmd="",
            activate_cmd="source ",
            deactivate_cmd="deactivate",
        ),
        "fish": ShellInfo(
            execute_cmd="fish",
            prompt_cmd="fish_prompt; echo ' '",
            activate_script="activate.fish",
            testscript_extension="",
            preamble_cmd="",
            activate_cmd="source ",
            deactivate_cmd="deactivate",
        ),
        "csh": ShellInfo(
            execute_cmd="csh",
            prompt_cmd=r"set | grep -E 'prompt\s' | sed -E 's/^prompt\s+(.*)$/\1/'",
            activate_script="activate.csh",
            testscript_extension="",
            preamble_cmd="set prompt=%",  # csh defaults to an unset 'prompt' in non-interactive shells
            activate_cmd="source ",
            deactivate_cmd="deactivate",
        ),
        "xonsh": ShellInfo(
            execute_cmd="xonsh",
            prompt_cmd="print(__xonsh__.shell.prompt)",
            activate_script="activate.xsh",
            testscript_extension="",
            preamble_cmd="$VIRTUAL_ENV = ''; $PROMPT = '{env_name}$ '",  # Sets consistent initial state
            activate_cmd="source ",
            deactivate_cmd="deactivate",
        ),
        "cmd": ShellInfo(
            execute_cmd="",
            prompt_cmd="echo %PROMPT%",
            activate_script="activate.bat",
            testscript_extension=".bat",
            preamble_cmd="@echo off & set PROMPT=$P$G",  # Sets consistent initial state
            activate_cmd="call ",
            deactivate_cmd="call deactivate",
        ),
        "powershell": ShellInfo(
            execute_cmd="powershell -File ",
            prompt_cmd="prompt",
            activate_script="activate.ps1",
            testscript_extension=".ps1",
            preamble_cmd="",
            activate_cmd=". ",
            deactivate_cmd="deactivate",
        ),
    }


@pytest.fixture(scope="function")
def clean_env():
    """Provide a fresh copy of the shell environment.

    VIRTUAL_ENV_DISABLE_PROMPT is always removed, if present, because
    the prompt tests assume it to be unset.

    """
    clean_env = os.environ.copy()
    clean_env.pop(env_compat(VIRTUAL_ENV_DISABLE_PROMPT), None)
    return clean_env


@pytest.mark.parametrize("shell", SHELL_LIST)
@pytest.mark.parametrize("env", [ENV_DEFAULT, ENV_CUSTOM])
@pytest.mark.parametrize(("value", "disable"), [("", False), ("0", True), ("1", True)])
def test_suppressed_prompt(shell, env, value, disable, get_work_root, clean_env, shell_info, platform_check_skip):
    """Confirm non-empty VIRTUAL_ENV_DISABLE_PROMPT suppresses prompt changes on activate."""
    skip_test = platform_check_skip(sys.platform, shell)
    if skip_test:
        pytest.skip(skip_test)

    script_name = SCRIPT_TEMPLATE.format(shell, "suppress", env, shell_info[shell].testscript_extension)
    output_name = OUTPUT_TEMPLATE.format(shell, "suppress", env)

    clean_env.update({env_compat(VIRTUAL_ENV_DISABLE_PROMPT): env_compat(value)})

    work_root = get_work_root(env)

    # The extra "{prompt}" here copes with some oddity of xonsh in certain emulated terminal
    # contexts: xonsh can dump stuff into the first line of the recorded script output,
    # so we have to include a dummy line of output that can get munged w/o consequence.
    with open(str(work_root[0] / script_name), "w") as f:
        f.write(
            dedent(
                """\
        {preamble}
        {prompt}
        {prompt}
        {act_cmd}{env}/{bindir}/{act_script}
        {prompt}
    """.format(
                    env=env,
                    act_cmd=shell_info[shell].activate_cmd,
                    preamble=shell_info[shell].preamble_cmd,
                    prompt=shell_info[shell].prompt_cmd,
                    act_script=shell_info[shell].activate_script,
                    bindir=work_root[1],
                )
            )
        )

    command = "{} {} > {}".format(shell_info[shell].execute_cmd, script_name, output_name)

    assert 0 == subprocess.call(command, cwd=str(work_root[0]), shell=True, env=clean_env)

    with open(str(work_root[0] / output_name), "rb") as f:
        lines = f.read().split(b"\n")

    # Is the prompt suppressed based on the env var value?
    assert (lines[1] == lines[2]) == disable, lines


@pytest.mark.parametrize("shell", SHELL_LIST)
@pytest.mark.parametrize(["env", "prefix"], [(ENV_DEFAULT, PREFIX_DEFAULT), (ENV_CUSTOM, PREFIX_CUSTOM)])
def test_activated_prompt(shell, env, prefix, get_work_root, shell_info, platform_check_skip, clean_env):
    """Confirm prompt modification behavior with and without --prompt specified."""
    skip_test = platform_check_skip(sys.platform, shell)
    if skip_test:
        pytest.skip(skip_test)

    # Cope with Azure DevOps terminal oddness for fish
    if shell == "fish":
        clean_env.update({env_compat("TERM"): env_compat("linux")})

    script_name = SCRIPT_TEMPLATE.format(shell, "normal", env, shell_info[shell].testscript_extension)
    output_name = OUTPUT_TEMPLATE.format(shell, "normal", env)

    work_root = get_work_root(env)

    # The extra "{prompt}" here copes with some oddity of xonsh in certain emulated terminal
    # contexts: xonsh can dump stuff into the first line of the recorded script output,
    # so we have to include a dummy line of output that can get munged w/o consequence.
    with open(str(work_root[0] / script_name), "w") as f:
        f.write(
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
                    act_cmd=shell_info[shell].activate_cmd,
                    deactivate=shell_info[shell].deactivate_cmd,
                    preamble=shell_info[shell].preamble_cmd,
                    prompt=shell_info[shell].prompt_cmd,
                    act_script=shell_info[shell].activate_script,
                    bindir=work_root[1],
                )
            )
        )

    command = "{} {} > {}".format(shell_info[shell].execute_cmd, script_name, output_name)

    assert 0 == subprocess.call(command, cwd=str(work_root[0]), shell=True, env=clean_env)

    with open(str(work_root[0] / output_name), "rb") as f:
        lines = f.read().split(b"\n")

    # Before activation and after deactivation
    assert lines[1] == lines[3], lines

    # Activated prompt. This construction allows coping with messes like fish's ANSI codes for colorizing.
    # The fish test is not as rigorous as I would like---it doesn't ensure no space is inserted between
    # a custom env prompt (argument to --prompt) and the base prompt---but it does provide assurance as
    # to the key pieces of content that should be present.
    # The stricter test for the other shells is satisfactory, though.
    before, env_marker, after = lines[2].partition(prefix.encode("utf-8"))
    assert env_marker != b"", lines

    # Separate handling for fish, which has color coding commands built into activate.fish that are
    # painful to work around; and for (t)csh on MacOS, which prepends extra text to
    # what gets sent to stdout
    if shell == "fish":
        # Looser assert
        assert lines[1] in after, lines
    elif shell == "csh" and IS_DARWIN:
        assert lines[1].endswith(after), lines
    else:
        # Stricter assert
        assert after == lines[1], lines
