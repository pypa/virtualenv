from __future__ import absolute_import, unicode_literals

import os
import pipes
import re
import subprocess
import sys
from os.path import dirname, normcase, realpath

import pytest
import six

from virtualenv.run import run_via_cli
from virtualenv.util import Path


class ActivationTester(object):
    def __init__(self, of_class, session, cmd, activate_script, extension):
        self.of_class = of_class
        self._creator = session.creator
        self._version_cmd = [cmd, "--version"]
        self._invoke_script = [cmd]
        self.activate_script = activate_script
        self.extension = extension
        self.activate_cmd = "source"
        self.deactivate = "deactivate"
        self.pydoc_call = "pydoc -w pydoc_test"

    def get_version(self, raise_on_fail):
        # locally we disable, so that contributors don't need to have everything setup
        try:
            process = subprocess.Popen(
                self._version_cmd, universal_newlines=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
            out, err = process.communicate()
            if out:
                return out
            return err
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
            _raw = subprocess.check_output(invoke, universal_newlines=True, stderr=subprocess.STDOUT, env=env)
            raw = "\n{}".format(six.ensure_text(_raw))
        except subprocess.CalledProcessError as exception:
            assert not exception.returncode, six.ensure_text(exception.output)
            return

        out = re.sub(r"pydev debugger: process \d+ is connecting\n\n", "", raw, re.M).strip().split("\n")
        self.assert_output(out, raw, tmp_path)
        return env, activate_script

    def non_source_activate(self, activate_script):
        return self._invoke_script + [str(activate_script)]

    # noinspection PyMethodMayBeStatic
    def env(self, tmp_path):
        env = os.environ.copy()
        # add the current python executable folder to the path so we already have another python on the path
        # also keep the path so the shells (fish, bash, etc can be discovered)
        env[str("PATH")] = os.pathsep.join([dirname(sys.executable)] + env.get(str("PATH"), str("")).split(os.pathsep))
        # clear up some environment variables so they don't affect the tests
        for key in [k for k in env.keys() if k.startswith("_OLD") or k.startswith("VIRTUALENV_")]:
            del env[key]
        return env

    def _generate_test_script(self, activate_script, tmp_path):
        commands = self._get_test_lines(activate_script)
        script = os.linesep.join(commands)
        test_script = tmp_path / "script.{}".format(self.extension)
        test_script.write_text(script, encoding='utf-8')
        return test_script

    def _get_test_lines(self, activate_script):
        commands = [
            self.print_python_exe(),
            self.print_os_env_var("VIRTUAL_ENV"),
            self.activate_call(activate_script),
            self.print_python_exe(),
            self.print_os_env_var("VIRTUAL_ENV"),
            # \\ loads documentation from the virtualenv site packages
            self.pydoc_call,
            self.deactivate,
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
        assert self.norm_path(out[2]) == self.norm_path(self._creator.exe), raw
        assert self.norm_path(out[3]) == self.norm_path(self._creator.dest_dir).replace("\\\\", "\\"), raw
        assert out[4] == "wrote pydoc_test.html"
        content = tmp_path / "pydoc_test.html"
        assert content.exists(), raw
        # post deactivation, same as before
        assert out[-2] == out[0], raw
        assert out[-1] == "None", raw

    def quote(self, s):
        return pipes.quote(s)

    def python_cmd(self, cmd):
        return "{} -c {}".format(os.path.basename(sys.executable), self.quote(cmd))

    def print_python_exe(self):
        return self.python_cmd("import sys; print(sys.executable)")

    def print_os_env_var(self, var):
        val = '"{}"'.format(var)
        return self.python_cmd("import os; print(os.environ.get({}, None))".format(val))

    def activate_call(self, script):
        cmd = self.quote(six.ensure_text(str(self.activate_cmd)))
        scr = self.quote(six.ensure_text(str(script)))
        return "{} {}".format(cmd, scr).strip()

    @staticmethod
    def norm_path(path):
        # python may return Windows short paths, normalize
        path = realpath(six.ensure_text(str(path)) if isinstance(path, Path) else path)
        if sys.platform == "win32":
            from ctypes import create_unicode_buffer, windll

            buffer_cont = create_unicode_buffer(256)
            get_long_path_name = windll.kernel32.GetLongPathNameW
            get_long_path_name(six.text_type(path), buffer_cont, 256)  # noqa: F821
            result = buffer_cont.value
        else:
            result = path
        return normcase(result)


class RaiseOnNonSourceCall(ActivationTester):
    def __init__(self, of_class, session, cmd, activate_script, extension, non_source_fail_message):
        super(RaiseOnNonSourceCall, self).__init__(of_class, session, cmd, activate_script, extension)
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
        assert self.non_source_fail_message in six.ensure_text(err)


@pytest.fixture(scope="session")
def activation_tester_class():
    return ActivationTester


@pytest.fixture(scope="session")
def raise_on_non_source_class():
    return RaiseOnNonSourceCall


@pytest.fixture(scope="session")
def activation_python(tmp_path_factory, special_char_name):
    dest = tmp_path_factory.mktemp(six.ensure_str(special_char_name))
    session = run_via_cli(["--seed", "none", str(dest), "--prompt", special_char_name])
    pydoc_test = session.creator.site_packages[0] / "pydoc_test.py"
    pydoc_test.write_text('"""This is pydoc_test.py"""')
    return session


@pytest.fixture()
def activation_tester(activation_python, monkeypatch, tmp_path, special_char_name, is_inside_ci):
    def _tester(tester_class):
        tester = tester_class(activation_python)
        if not tester.of_class.supports(activation_python.creator.interpreter):
            pytest.skip("{} not supported on current environment".format(tester.of_class.__name__))
        version = tester.get_version(raise_on_fail=is_inside_ci)
        if not isinstance(version, six.string_types):
            pytest.skip(msg=six.text_type(version))
        folder = tmp_path / special_char_name
        folder.mkdir()
        return tester(monkeypatch, folder)

    return _tester
