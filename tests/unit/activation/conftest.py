from __future__ import absolute_import, unicode_literals

import os
import pipes
import re
import shutil
import subprocess
import sys
from os.path import dirname, normcase

import pytest
import six

from virtualenv.info import IS_PYPY, WIN_CPYTHON_2
from virtualenv.run import cli_run
from virtualenv.util.path import Path
from virtualenv.util.six import ensure_str, ensure_text
from virtualenv.util.subprocess import Popen


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
        self.script_encoding = "utf-8"
        self._version = None
        self.unix_line_ending = True

    def get_version(self, raise_on_fail):
        if self._version is None:
            # locally we disable, so that contributors don't need to have everything setup
            try:
                process = Popen(
                    self._version_cmd,
                    universal_newlines=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
                out, err = process.communicate()
                result = out if out else err
                self._version = result
                return result
            except Exception as exception:
                self._version = exception
                if raise_on_fail:
                    raise
                return RuntimeError("{} is not available due {}".format(self, exception))
        return self._version

    def __unicode__(self):
        return "{}(\nversion={!r},\ncreator={},\ninterpreter={})".format(
            self.__class__.__name__,
            self._version,
            six.text_type(self._creator),
            six.text_type(self._creator.interpreter),
        )

    def __repr__(self):
        return ensure_str(self.__unicode__())

    def __call__(self, monkeypatch, tmp_path):
        activate_script = self._creator.bin_dir / self.activate_script

        # check line endings are correct type
        script_content = activate_script.read_bytes()
        for line in script_content.split(b"\n")[:-1]:
            cr = b"\r" if sys.version_info.major == 2 else 13
            if self.unix_line_ending:
                assert line == b"" or line[-1] != cr, script_content.decode("utf-8")
            else:
                assert line[-1] == cr, script_content.decode("utf-8")

        test_script = self._generate_test_script(activate_script, tmp_path)
        monkeypatch.chdir(ensure_text(str(tmp_path)))

        monkeypatch.delenv(str("VIRTUAL_ENV"), raising=False)
        invoke, env = self._invoke_script + [ensure_text(str(test_script))], self.env(tmp_path)

        try:
            process = Popen(invoke, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env)
            _raw, _ = process.communicate()
            raw = _raw.decode("utf-8")
        except subprocess.CalledProcessError as exception:
            output = ensure_text((exception.output + exception.stderr) if six.PY3 else exception.output)
            assert not exception.returncode, output
            return

        out = re.sub(r"pydev debugger: process \d+ is connecting\n\n", "", raw, re.M).strip().splitlines()
        self.assert_output(out, raw, tmp_path)
        return env, activate_script

    def non_source_activate(self, activate_script):
        return self._invoke_script + [str(activate_script)]

    # noinspection PyMethodMayBeStatic
    def env(self, tmp_path):
        env = os.environ.copy()
        # add the current python executable folder to the path so we already have another python on the path
        # also keep the path so the shells (fish, bash, etc can be discovered)
        env[str("PYTHONIOENCODING")] = str("utf-8")
        env[str("PATH")] = os.pathsep.join([dirname(sys.executable)] + env.get(str("PATH"), str("")).split(os.pathsep))
        # clear up some environment variables so they don't affect the tests
        for key in [k for k in env.keys() if k.startswith(str("_OLD")) or k.startswith(str("VIRTUALENV_"))]:
            del env[key]
        return env

    def _generate_test_script(self, activate_script, tmp_path):
        commands = self._get_test_lines(activate_script)
        script = ensure_text(os.linesep).join(commands)
        test_script = tmp_path / "script.{}".format(self.extension)
        with open(ensure_text(str(test_script)), "wb") as file_handler:
            file_handler.write(script.encode(self.script_encoding))
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
        expected = self._creator.exe.parent / os.path.basename(sys.executable)
        assert self.norm_path(out[2]) == self.norm_path(expected), raw
        assert self.norm_path(out[3]) == self.norm_path(self._creator.dest).replace("\\\\", "\\"), raw
        assert out[4] == "wrote pydoc_test.html", raw
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
        return self.python_cmd(
            "import sys; print(sys.executable{})".format(
                "" if six.PY3 or IS_PYPY else ".decode(sys.getfilesystemencoding())",
            ),
        )

    def print_os_env_var(self, var):
        val = '"{}"'.format(var)
        return self.python_cmd(
            "import os; import sys; v = os.environ.get({}); print({})".format(
                val,
                "v" if six.PY3 or IS_PYPY else "None if v is None else v.decode(sys.getfilesystemencoding())",
            ),
        )

    def activate_call(self, script):
        cmd = self.quote(ensure_text(str(self.activate_cmd)))
        scr = self.quote(ensure_text(str(script)))
        return "{} {}".format(cmd, scr).strip()

    @staticmethod
    def norm_path(path):
        # python may return Windows short paths, normalize
        if not isinstance(path, Path):
            path = Path(path)
        path = ensure_text(str(path.resolve()))
        if sys.platform != "win32":
            result = path
        else:
            from ctypes import create_unicode_buffer, windll

            buffer_cont = create_unicode_buffer(256)
            get_long_path_name = windll.kernel32.GetLongPathNameW
            get_long_path_name(six.text_type(path), buffer_cont, 256)
            result = buffer_cont.value or path
        return normcase(result)


class RaiseOnNonSourceCall(ActivationTester):
    def __init__(self, of_class, session, cmd, activate_script, extension, non_source_fail_message):
        super(RaiseOnNonSourceCall, self).__init__(of_class, session, cmd, activate_script, extension)
        self.non_source_fail_message = non_source_fail_message

    def __call__(self, monkeypatch, tmp_path):
        env, activate_script = super(RaiseOnNonSourceCall, self).__call__(monkeypatch, tmp_path)
        process = Popen(
            self.non_source_activate(activate_script),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
        )
        out, _err = process.communicate()
        err = _err.decode("utf-8")
        assert process.returncode
        assert self.non_source_fail_message in err


@pytest.fixture(scope="session")
def activation_tester_class():
    return ActivationTester


@pytest.fixture(scope="session")
def raise_on_non_source_class():
    return RaiseOnNonSourceCall


@pytest.fixture(scope="session", params=[True, False], ids=["with_prompt", "no_prompt"])
def activation_python(request, tmp_path_factory, special_char_name, current_fastest):
    dest = os.path.join(ensure_text(str(tmp_path_factory.mktemp("activation-tester-env"))), special_char_name)
    cmd = ["--without-pip", dest, "--creator", current_fastest, "-vv", "--no-periodic-update"]
    if request.param:
        cmd += ["--prompt", special_char_name]
    session = cli_run(cmd)
    pydoc_test = session.creator.purelib / "pydoc_test.py"
    pydoc_test.write_text('"""This is pydoc_test.py"""')
    yield session
    if WIN_CPYTHON_2:  # PY2 windows does not support unicode delete
        shutil.rmtree(dest)


@pytest.fixture()
def activation_tester(activation_python, monkeypatch, tmp_path, is_inside_ci):
    def _tester(tester_class):
        tester = tester_class(activation_python)
        if not tester.of_class.supports(activation_python.creator.interpreter):
            pytest.skip("{} not supported".format(tester.of_class.__name__))
        version = tester.get_version(raise_on_fail=is_inside_ci)
        if not isinstance(version, six.string_types):
            pytest.skip(msg=six.text_type(version))
        return tester(monkeypatch, tmp_path)

    return _tester
