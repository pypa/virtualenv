from __future__ import annotations

import os
import re
import subprocess
import sys
from os.path import dirname, normcase
from pathlib import Path
from shlex import quote
from subprocess import Popen

import pytest

from virtualenv.run import cli_run


class ActivationTester:
    def __init__(self, of_class, session, cmd, activate_script, extension) -> None:
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
                    encoding="utf-8",
                )
                out, err = process.communicate()
            except Exception as exception:
                self._version = exception
                if raise_on_fail:
                    raise
                return RuntimeError(f"{self} is not available due {exception}")
            else:
                result = out or err
                self._version = result
                return result
        return self._version

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}(\nversion={self._version!r},\ncreator={self._creator},\n"
            f"interpreter={self._creator.interpreter})"
        )

    def __call__(self, monkeypatch, tmp_path):
        activate_script = self._creator.bin_dir / self.activate_script

        # check line endings are correct type
        script_content = activate_script.read_bytes()
        for line in script_content.split(b"\n")[:-1]:
            if self.unix_line_ending:
                assert line == b"" or line[-1] != 13, script_content.decode("utf-8")
            else:
                assert line[-1] == 13, script_content.decode("utf-8")

        test_script = self._generate_test_script(activate_script, tmp_path)
        monkeypatch.chdir(tmp_path)

        monkeypatch.delenv("VIRTUAL_ENV", raising=False)
        invoke, env = [*self._invoke_script, str(test_script)], self.env(tmp_path)

        try:
            process = Popen(invoke, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env)
            raw_, _ = process.communicate()
            raw = raw_.decode()
            assert process.returncode == 0, raw
        except subprocess.CalledProcessError as exception:
            output = exception.output + exception.stderr
            assert not exception.returncode, output  # noqa: PT017
            return None

        out = re.sub(r"pydev debugger: process \d+ is connecting\n\n", "", raw, flags=re.MULTILINE).strip().splitlines()
        self.assert_output(out, raw, tmp_path)
        return env, activate_script

    def non_source_activate(self, activate_script):
        return [*self._invoke_script, str(activate_script)]

    def env(self, tmp_path):  # noqa: ARG002
        env = os.environ.copy()
        # add the current python executable folder to the path so we already have another python on the path
        # also keep the path so the shells (fish, bash, etc can be discovered)
        env["PYTHONIOENCODING"] = "utf-8"
        env["PATH"] = os.pathsep.join([dirname(sys.executable), *env.get("PATH", "").split(os.pathsep)])
        # clear up some environment variables so they don't affect the tests
        for key in [k for k in env if k.startswith(("_OLD", "VIRTUALENV_"))]:
            del env[key]
        return env

    def _generate_test_script(self, activate_script, tmp_path):
        commands = self._get_test_lines(activate_script)
        script = os.linesep.join(commands)
        test_script = tmp_path / f"script.{self.extension}"
        with test_script.open("wb") as file_handler:
            file_handler.write(script.encode(self.script_encoding))
        return test_script

    def _get_test_lines(self, activate_script):
        return [
            self.print_python_exe(),
            self.print_os_env_var("VIRTUAL_ENV"),
            self.print_os_env_var("VIRTUAL_ENV_PROMPT"),
            self.activate_call(activate_script),
            self.print_python_exe(),
            self.print_os_env_var("VIRTUAL_ENV"),
            self.print_os_env_var("VIRTUAL_ENV_PROMPT"),
            self.print_prompt(),
            # \\ loads documentation from the virtualenv site packages
            self.pydoc_call,
            self.deactivate,
            self.print_python_exe(),
            self.print_os_env_var("VIRTUAL_ENV"),
            self.print_os_env_var("VIRTUAL_ENV_PROMPT"),
            "",  # just finish with an empty new line
        ]

    def assert_output(self, out, raw, tmp_path):
        # pre-activation
        assert out[0], raw
        assert out[1] == "None", raw
        assert out[2] == "None", raw
        # post-activation
        expected = self._creator.exe.parent / os.path.basename(sys.executable)
        assert self.norm_path(out[3]) == self.norm_path(expected), raw
        assert self.norm_path(out[4]) == self.norm_path(self._creator.dest).replace("\\\\", "\\"), raw
        assert out[5] == self._creator.env_name
        # Some attempts to test the prompt output print more than 1 line.
        # So we need to check if the prompt exists on any of them.
        prompt_text = f"({self._creator.env_name}) "
        assert any(prompt_text in line for line in out[6:-4]), raw

        assert out[-4] == "wrote pydoc_test.html", raw
        content = tmp_path / "pydoc_test.html"
        assert content.exists(), raw
        # post deactivation, same as before
        assert out[-3] == out[0], raw
        assert out[-2] == "None", raw
        assert out[-1] == "None", raw

    def quote(self, s):
        return quote(s)

    def python_cmd(self, cmd):
        return f"{os.path.basename(sys.executable)} -c {self.quote(cmd)}"

    def print_python_exe(self):
        return self.python_cmd("import sys; print(sys.executable)")

    def print_os_env_var(self, var):
        val = f'"{var}"'
        return self.python_cmd(f"import os; import sys; v = os.environ.get({val}); print(v)")

    def print_prompt(self):
        return NotImplemented

    def activate_call(self, script):
        cmd = self.quote(str(self.activate_cmd))
        scr = self.quote(str(script))
        return f"{cmd} {scr}".strip()

    @staticmethod
    def norm_path(path):
        # python may return Windows short paths, normalize
        if not isinstance(path, Path):
            path = Path(path)
        path = str(path.resolve())
        if sys.platform != "win32":
            result = path
        else:
            from ctypes import create_unicode_buffer, windll  # noqa: PLC0415

            buffer_cont = create_unicode_buffer(256)
            get_long_path_name = windll.kernel32.GetLongPathNameW
            get_long_path_name(str(path), buffer_cont, 256)
            result = buffer_cont.value or path
        return normcase(result)


class RaiseOnNonSourceCall(ActivationTester):
    def __init__(  # noqa: PLR0913
        self,
        of_class,
        session,
        cmd,
        activate_script,
        extension,
        non_source_fail_message,
    ) -> None:
        super().__init__(of_class, session, cmd, activate_script, extension)
        self.non_source_fail_message = non_source_fail_message

    def __call__(self, monkeypatch, tmp_path):
        env, activate_script = super().__call__(monkeypatch, tmp_path)
        process = Popen(
            self.non_source_activate(activate_script),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
        )
        _out, _err = process.communicate()
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
    dest = os.path.join(str(tmp_path_factory.mktemp("activation-tester-env")), special_char_name)
    cmd = ["--without-pip", dest, "--creator", current_fastest, "-vv", "--no-periodic-update"]
    if request.param:
        cmd += ["--prompt", special_char_name]
    session = cli_run(cmd)
    pydoc_test = session.creator.purelib / "pydoc_test.py"
    pydoc_test.write_text('"""This is pydoc_test.py"""', encoding="utf-8")
    return session


@pytest.fixture
def activation_tester(activation_python, monkeypatch, tmp_path, is_inside_ci):
    def _tester(tester_class):
        tester = tester_class(activation_python)
        if not tester.of_class.supports(activation_python.creator.interpreter):
            pytest.skip(f"{tester.of_class.__name__} not supported")
        version = tester.get_version(raise_on_fail=is_inside_ci)
        if not isinstance(version, str):
            pytest.skip(reason=str(version))
        return tester(monkeypatch, tmp_path)

    return _tester
