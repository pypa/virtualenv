from __future__ import absolute_import, unicode_literals

import inspect
import os
import pipes
import re
import subprocess
import sys
from os.path import dirname, normcase, realpath

import pytest
import six

from virtualenv.activation import (
    BashActivator,
    CShellActivator,
    DOSActivator,
    FishActivator,
    PowerShellActivator,
    PythonActivator,
    XonoshActivator,
)
from virtualenv.interpreters.discovery.py_info import CURRENT
from virtualenv.run import collect_activators, run_via_cli


def norm_path(path):
    # python may return Windows short paths, normalize
    path = realpath(str(path))
    if sys.platform == "win32":
        from ctypes import create_unicode_buffer, windll

        buffer_cont = create_unicode_buffer(256)
        get_long_path_name = windll.kernel32.GetLongPathNameW
        get_long_path_name(six.text_type(path), buffer_cont, 256)  # noqa: F821
        result = buffer_cont.value
    else:
        result = path
    return normcase(result)


class ActivationTester(object):
    def __init__(self, session, cmd, activate_script, extension):
        self._creator = session.creator
        self.cmd = cmd
        self._version_cmd = [cmd, "--version"]
        self._invoke_script = [cmd]
        self.activate_script = activate_script
        self.activate_cmd = "source"
        self.extension = extension

    def get_version(self, raise_on_fail):
        # locally we disable, so that contributors don't need to have everything setup
        try:
            return subprocess.check_output(self._version_cmd, universal_newlines=True)
        except Exception as exception:
            if raise_on_fail:
                raise
            return RuntimeError("{} is not available due {}".format(self, exception))

    def __call__(self, monkeypatch, tmp_path):
        activate_script = self._creator.bin_dir / self.activate_script
        test_script = self._generate_test_script(activate_script, tmp_path)
        monkeypatch.chdir(tmp_path)

        monkeypatch.delenv(str("VIRTUAL_ENV"), raising=False)
        invoke, env = self._invoke_script + [str(test_script)], self.env(tmp_path)

        try:
            raw = subprocess.check_output(invoke, universal_newlines=True, stderr=subprocess.STDOUT, env=env)
        except subprocess.CalledProcessError as exception:
            assert not exception.returncode, exception.output
            return
        out = re.sub(r"pydev debugger: process \d+ is connecting\n\n", "", raw, re.M).strip().split("\n")
        self.assert_output(out, raw, tmp_path)
        return env, activate_script

    def non_source_activate(self, activate_script):
        return self._invoke_script + [str(activate_script)]

    def env(self, tmp_path):
        return None

    def _generate_test_script(self, activate_script, tmp_path):
        commands = self._get_test_lines(activate_script)
        script = os.linesep.join(commands)
        test_script = tmp_path / "script.{}".format(self.extension)
        test_script.write_text(script)
        return test_script

    def _get_test_lines(self, activate_script):
        commands = [
            self.print_python_exe(),
            self.print_os_env_var("VIRTUAL_ENV"),
            self.activate_call(activate_script),
            self.print_python_exe(),
            self.print_os_env_var("VIRTUAL_ENV"),
            # pydoc loads documentation from the virtualenv site packages
            "pydoc -w pydoc_test",
            "deactivate",
            self.print_python_exe(),
            self.print_os_env_var("VIRTUAL_ENV"),
            "",  # just finish with an empty new line
        ]
        return commands

    def assert_output(self, out, raw, tmp_path):
        # pre-activation
        assert out[0], raw
        assert out[1] == "None", raw
        # post-activation
        assert norm_path(out[2]) == norm_path(self._creator.exe), raw
        assert norm_path(out[3]) == norm_path(self._creator.dest_dir).replace("\\\\", "\\"), raw
        assert out[4] == "wrote pydoc_test.html"
        content = tmp_path / "pydoc_test.html"
        assert content.exists(), raw
        # post deactivation, same as before
        assert out[-2] == out[0], raw
        assert out[-1] == "None", raw

    def quote(self, s):
        return pipes.quote(s)

    def python_cmd(self, cmd):
        return "{} -c {}".format(self.quote(str(self._creator.exe)), self.quote(cmd))

    def print_python_exe(self):
        return self.python_cmd("import sys; print(sys.executable)")

    def print_os_env_var(self, var):
        val = '"{}"'.format(var)
        return self.python_cmd("import os; print(os.environ.get({}, None))".format(val))

    def activate_call(self, script):
        return "{} {}".format(pipes.quote(str(self.activate_cmd)), pipes.quote(str(script))).strip()


class RaiseOnNonSourceCall(ActivationTester):
    def __init__(self, session, cmd, activate_script, extension, non_source_fail_message):
        super(RaiseOnNonSourceCall, self).__init__(session, cmd, activate_script, extension)
        self.non_source_fail_message = non_source_fail_message

    def __call__(self, monkeypatch, tmp_path):
        env, activate_script = super(RaiseOnNonSourceCall, self).__call__(monkeypatch, tmp_path)
        process = subprocess.Popen(
            self.non_source_activate(activate_script),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            universal_newlines=True,
        )
        out, err = process.communicate()
        assert process.returncode
        assert self.non_source_fail_message in err


class Bash(RaiseOnNonSourceCall):
    def __init__(self, session):
        super(Bash, self).__init__(session, "bash", "activate.sh", "sh", "You must source this script: $ source ")


class Csh(ActivationTester):
    def __init__(self, session):
        super(Csh, self).__init__(session, "csh", "activate.csh", "csh")


class DOS(ActivationTester):
    def __init__(self, session):
        super(DOS, self).__init__(session, "bat", "activate.bat", "cmd")


class Fish(ActivationTester):
    def __init__(self, session):
        super(Fish, self).__init__(session, "fish", "activate.fish", "fish")


def win_exe(cmd):
    return "{}{}".format(cmd, ".exe" if sys.platform == "win32" else "")


class PowerShell(ActivationTester):
    def __init__(self, session):
        cmd = "powershell.exe" if sys.platform == "win32" else "pwsh"
        super(PowerShell, self).__init__(session, cmd, "activate.ps1", "ps1")
        self._version_cmd = [self.cmd, "-c", "$PSVersionTable"]
        self.activate_cmd = "."

    def quote(self, s):
        """powershell double double quote needed for quotes within single quotes"""
        return pipes.quote(s).replace('"', '""')

    def invoke_script(self):
        return [self.cmd, "-File"]


class Xonosh(ActivationTester):
    def __init__(self, session):
        super(Xonosh, self).__init__(session, "xonsh", "activate.xsh", "xsh")
        self._invoke_script = [sys.executable, "-m", "xonsh"]
        self.__version_cmd = [sys.executable, "-m", "xonsh", "--version"]

    def env(self, tmp_path):
        env = os.environ.copy()
        env[str("PATH")] = os.pathsep.join([dirname(sys.executable)] + env.get(str("PATH"), str("")).split(os.pathsep))
        env.update({"XONSH_DEBUG": "1", "XONSH_SHOW_TRACEBACK": "True"})
        return env

    def activate_call(self, script):
        return "{} {}".format(self.activate_cmd, repr(str(script))).strip()


class Python(RaiseOnNonSourceCall):
    def __init__(self, session):
        super(Python, self).__init__(
            session,
            sys.executable,
            activate_script="activate_this.py",
            extension="py",
            non_source_fail_message="You must use exec(open(this_file).read(), {'__file__': this_file}))",
        )

    def env(self, tmp_path):
        env = os.environ.copy()
        for key in {"VIRTUAL_ENV", "PYTHONPATH"}:
            env.pop(str(key), None)
        env[str("PATH")] = os.pathsep.join([str(tmp_path), str(tmp_path / "other")])
        return env

    def _get_test_lines(self, activate_script):
        raw = inspect.getsource(self.activate_this_test)
        raw = raw.replace("__FILENAME__", str(activate_script))
        return [i.lstrip() for i in raw.splitlines()[2:]]

    # noinspection PyUnresolvedReferences
    @staticmethod
    def activate_this_test():
        import os
        import sys

        print(os.environ.get("VIRTUAL_ENV"))
        print(os.environ.get("PATH"))
        print(os.pathsep.join(sys.path))
        file_at = r"__FILENAME__"
        exec(open(file_at).read(), {"__file__": file_at})
        print(os.environ.get("VIRTUAL_ENV"))
        print(os.environ.get("PATH"))
        print(os.pathsep.join(sys.path))
        import inspect
        import pydoc_test

        print(inspect.getsourcefile(pydoc_test))

    def assert_output(self, out, raw, tmp_path):
        assert out[0] == "None"  # start with VIRTUAL_ENV None

        prev_path = out[1].split(os.path.pathsep)
        prev_sys_path = out[2].split(os.path.pathsep)

        assert out[3] == str(self._creator.dest_dir)  # VIRTUAL_ENV now points to the virtual env folder

        new_path = out[4].split(os.pathsep)  # PATH now starts with bin path of current
        assert ([str(self._creator.bin_dir)] + prev_path) == new_path

        # sys path contains the site package at its start
        new_sys_path = out[5].split(os.path.pathsep)
        assert ([str(i) for i in self._creator.site_packages] + prev_sys_path) == new_sys_path

        # manage to import from activate site package
        assert norm_path(out[6]) == norm_path(self._creator.site_packages[0] / "pydoc_test.py")

    def non_source_activate(self, activate_script):
        return self._invoke_script + ["-c", 'exec(open(r"{}").read())'.format(activate_script)]


ACTIVATION_TEST = {
    BashActivator: Bash,
    PowerShellActivator: PowerShell,
    CShellActivator: Csh,
    XonoshActivator: Xonosh,
    FishActivator: Fish,
    PythonActivator: Python,
    DOSActivator: DOS,
}
IS_INSIDE_CI = "CI_RUN" in os.environ


@pytest.fixture(scope="session")
def activation_python(tmp_path_factory):
    dest = tmp_path_factory.mktemp("a")
    session = run_via_cli(["--seed", "none", str(dest)])
    pydoc_test = session.creator.site_packages[0] / "pydoc_test.py"
    pydoc_test.write_text('"""This is pydoc_test.py"""')
    return session


@pytest.fixture(params=list(collect_activators(CURRENT).values()), scope="session")
def activator(request, tmp_path_factory, activation_python):
    tester_class = ACTIVATION_TEST[request.param]
    tester = tester_class(activation_python)
    version = tester.get_version(raise_on_fail=IS_INSIDE_CI)
    if not isinstance(version, six.string_types):
        pytest.skip(msg=six.text_type(version))
    return tester


def test_activation(activation_python, activator, monkeypatch, tmp_path):
    activator(monkeypatch, tmp_path)
