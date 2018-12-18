from __future__ import absolute_import, unicode_literals

import os
import pipes
import subprocess
import sys
from os.path import dirname, join, normcase

import pytest
import six

import virtualenv

IS_INSIDE_CI = "CI_RUN" in os.environ


def need_executable(name, check_cmd):
    """skip running this locally if executable not found, unless we're inside the CI"""

    def wrapper(fn):
        fn = getattr(pytest.mark, name)(fn)
        try:
            fn.version = subprocess.check_output(check_cmd)
        except OSError:
            if IS_INSIDE_CI:
                return fn  # let the test fail in CI
            # locally we disable, so that contributors don't need to have everything setup
            return pytest.mark.skip(reason="{} is not available".format(name))(fn)
        return fn

    return wrapper


def requires(on):
    def wrapper(fn):
        return need_executable(on.cmd.replace(".exe", ""), (on.check))(fn)

    return wrapper


def norm_long_path(short_path_name):
    # python may return Windows short paths, normalize
    if virtualenv.is_win:
        from ctypes import create_unicode_buffer, windll

        buffer_cont = create_unicode_buffer(256)
        get_long_path_name = windll.kernel32.GetLongPathNameW
        get_long_path_name(six.text_type(short_path_name), buffer_cont, 256)  # noqa: F821
        result = buffer_cont.value
    else:
        result = short_path_name
    return normcase(result)


@pytest.fixture(scope="session")
def activation_env(tmp_path_factory):
    path = tmp_path_factory.mktemp("activation-test-env")
    prev_cwd = os.getcwd()
    try:
        os.chdir(str(path))
        home_dir, _, __, bin_dir = virtualenv.path_locations(str(path / "env"))
        virtualenv.create_environment(home_dir, no_pip=True, no_setuptools=True, no_wheel=True)
        yield home_dir, bin_dir
    finally:
        os.chdir(str(prev_cwd))


class Activation(object):
    cmd = ""
    extension = "test"
    invoke_script = []
    command_separator = os.linesep
    activate_cmd = "source"
    activate_script = ""
    check_has_exe = []
    check = []

    def __init__(self, activation_env, tmp_path):
        self.home_dir = activation_env[0]
        self.bin_dir = activation_env[1]
        self.path = tmp_path

    def quote(self, s):
        return pipes.quote(s)

    def python_cmd(self, cmd):
        return "{} -c {}".format(self.quote(virtualenv.expected_exe), self.quote(cmd))

    def python_script(self, script):
        return "{} {}".format(self.quote(virtualenv.expected_exe), self.quote(script))

    def print_python_exe(self):
        return self.python_cmd("import sys; print(sys.executable)")

    def print_os_env_var(self, var):
        val = '"{}"'.format(var)
        return self.python_cmd("import os; print(os.environ.get({}, None))".format(val))

    def __call__(self, monkeypatch):
        absolute_activate_script = norm_long_path(join(self.bin_dir, self.activate_script))

        site_packages = subprocess.check_output(
            [
                os.path.join(self.bin_dir, virtualenv.expected_exe),
                "-c",
                "from distutils.sysconfig import get_python_lib; print(get_python_lib())",
            ],
            universal_newlines=True,
        ).strip()
        pydoc_test = self.path.__class__(site_packages) / "pydoc_test.py"
        pydoc_test.write_text('"""This is pydoc_test.py"""')

        commands = [
            self.print_python_exe(),
            self.print_os_env_var("VIRTUAL_ENV"),
            "{} {}".format(pipes.quote(self.activate_cmd), pipes.quote(absolute_activate_script)).strip(),
            self.print_python_exe(),
            self.print_os_env_var("VIRTUAL_ENV"),
            # pydoc loads documentation from the virtualenv site packages
            "pydoc -w pydoc_test",
            "deactivate",
            self.print_python_exe(),
            self.print_os_env_var("VIRTUAL_ENV"),
            "",  # just finish with an empty new line
        ]
        script = self.command_separator.join(commands)
        test_script = self.path / "script.{}".format(self.extension)
        test_script.write_text(script)
        assert test_script.exists()

        monkeypatch.chdir(str(self.path))
        invoke_shell = self.invoke_script + [str(test_script)]

        monkeypatch.delenv(str("VIRTUAL_ENV"), raising=False)

        # in case the tool is provided by the dev environment (e.g. xonosh)
        env = os.environ.copy()
        env[str("PATH")] = os.pathsep.join([dirname(sys.executable)] + env.get(str("PATH"), str("")).split(os.pathsep))

        raw = subprocess.check_output(invoke_shell, universal_newlines=True, stderr=subprocess.STDOUT, env=env)
        out = raw.strip().split("\n")

        # pre-activation
        assert out[0], raw
        assert out[1] == "None", raw

        # post-activation
        exe = "{}.exe".format(virtualenv.expected_exe) if virtualenv.is_win else virtualenv.expected_exe
        assert norm_long_path(out[2]) == norm_long_path(join(self.bin_dir, exe)), raw
        assert norm_long_path(out[3]) == norm_long_path(str(self.home_dir)).replace("\\\\", "\\"), raw

        assert out[4] == "wrote pydoc_test.html"
        content = self.path / "pydoc_test.html"
        assert content.exists(), raw

        # post deactivation, same as before
        assert out[-2] == out[0], raw
        assert out[-1] == "None", raw


class BashActivation(Activation):
    cmd = "bash.exe" if virtualenv.is_win else "bash"
    invoke_script = [cmd]
    extension = "sh"
    activate_script = "activate"
    check = [cmd, "--version"]


@pytest.mark.skipif(sys.platform == "win32", reason="no sane way to provision bash on Windows yet")
@requires(BashActivation)
def test_bash(activation_env, monkeypatch, tmp_path):
    BashActivation(activation_env, tmp_path)(monkeypatch)


class CshActivation(Activation):
    cmd = "csh.exe" if virtualenv.is_win else "csh"
    invoke_script = [cmd]
    extension = "csh"
    activate_script = "activate.csh"
    check = [cmd, "--version"]


@pytest.mark.skipif(sys.platform == "win32", reason="no sane way to provision csh on Windows yet")
@requires(CshActivation)
def test_csh(activation_env, monkeypatch, tmp_path):
    CshActivation(activation_env, tmp_path)(monkeypatch)


class FishActivation(Activation):
    cmd = "fish.exe" if virtualenv.is_win else "fish"
    invoke_script = [cmd]
    extension = "fish"
    activate_script = "activate.fish"
    check = [cmd, "--version"]


@pytest.mark.skipif(sys.platform == "win32", reason="no sane way to provision fish on Windows yet")
@requires(FishActivation)
def test_fish(activation_env, monkeypatch, tmp_path):
    FishActivation(activation_env, tmp_path)(monkeypatch)


class PowershellActivation(Activation):
    cmd = "powershell.exe" if virtualenv.is_win else "pwsh"
    extension = "ps1"
    invoke_script = [cmd, "-File"]
    activate_script = "activate.ps1"
    activate_cmd = "."
    check = [cmd, "-c", "$PSVersionTable"]

    @staticmethod
    def quote(s):
        """powershell double double quote needed for quotes within single quotes"""
        return pipes.quote(s).replace('"', '""')


@requires(PowershellActivation)
def test_powershell(activation_env, monkeypatch, tmp_path):
    PowershellActivation(activation_env, tmp_path)(monkeypatch)


class XonoshActivation(Activation):
    cmd = "xonsh"
    extension = "xsh"
    invoke_script = [cmd]
    activate_script = "activate.xsh"
    check = [cmd, "--version"]


@pytest.mark.skipif(sys.version_info < (3, 4), reason="xonosh requires Python 3.4 at least")
@requires(XonoshActivation)
def test_xonosh(activation_env, monkeypatch, tmp_path):
    XonoshActivation(activation_env, tmp_path)(monkeypatch)
