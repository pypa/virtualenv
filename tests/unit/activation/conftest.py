from __future__ import annotations

import os
import re
import subprocess
import sys
from os.path import dirname, normcase
from pathlib import Path
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
                    stdin=subprocess.DEVNULL,
                    universal_newlines=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    encoding="utf-8",
                )
                out, err = process.communicate(timeout=30)
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
            process = Popen(invoke, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env)
            raw_, _ = process.communicate(timeout=60)
        except subprocess.TimeoutExpired as exc:
            process.kill()
            remaining, _ = process.communicate(timeout=5)
            partial = (exc.stdout or b"") + (remaining or b"")
            pytest.fail(
                f"Activation script timed out:\nPartial output:\n{partial.decode(errors='replace')}\nCommand: {invoke}"
            )
        except subprocess.CalledProcessError as exception:
            output = exception.output + exception.stderr
            assert not exception.returncode, output  # ruff:ignore[pytest-assert-in-except]
            return None
        else:
            raw = raw_.decode(errors="replace")
            assert process.returncode == 0, raw

        out = re.sub(r"pydev debugger: process \d+ is connecting\n\n", "", raw, flags=re.MULTILINE).strip().splitlines()
        self.assert_output(out, raw, tmp_path)
        return env, activate_script

    def non_source_activate(self, activate_script):
        return [*self._invoke_script, str(activate_script)]

    def env(self, tmp_path):  # ruff:ignore[unused-method-argument]
        env = os.environ.copy()
        # add the current python executable folder to the path so we already have another python on the path
        # also keep the path so the shells (fish, bash, etc can be discovered)
        env["PYTHONIOENCODING"] = "utf-8"
        env["PATH"] = os.pathsep.join([dirname(sys.executable), *env.get("PATH", "").split(os.pathsep)])
        # clear up some environment variables so they don't affect the tests
        for key in [k for k in env if k.startswith(("_OLD", "VIRTUALENV_", "COVERAGE_"))]:
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
        steps = [
            self.print_python_exe(),
            self.print_os_env_var("VIRTUAL_ENV"),
            self.print_os_env_var("VIRTUAL_ENV_PROMPT"),
            self.print_os_env_var("TCL_LIBRARY"),
            self.print_os_env_var("TK_LIBRARY"),
            self.print_os_env_var("PKG_CONFIG_PATH"),
            self.activate_call(activate_script),
            self.print_python_exe(),
            self.print_os_env_var("VIRTUAL_ENV"),
            self.print_os_env_var("VIRTUAL_ENV_PROMPT"),
            self.print_os_env_var("TCL_LIBRARY"),
            self.print_os_env_var("TK_LIBRARY"),
            self.print_os_env_var("PKG_CONFIG_PATH"),
            self.print_prompt(),
            # \\ loads documentation from the virtualenv site packages
            self.pydoc_call,
            self.deactivate,
            self.print_python_exe(),
            self.print_os_env_var("VIRTUAL_ENV"),
            self.print_os_env_var("VIRTUAL_ENV_PROMPT"),
            self.print_os_env_var("TCL_LIBRARY"),
            self.print_os_env_var("TK_LIBRARY"),
            self.print_os_env_var("PKG_CONFIG_PATH"),
            "",  # just finish with an empty new line
        ]
        result = []
        for index, step in enumerate(steps):
            result.extend((self.print_marker(index), step))
        return result

    def print_marker(self, step) -> str:
        return f'echo "__STEP_{step}__"'

    def assert_output(self, out, raw, tmp_path) -> None:
        """Compare _get_test_lines() with the expected values."""
        out = [line for line in out if not line.strip('"').startswith("__STEP_")]
        assert out[0], raw
        assert out[1] == "None", raw
        assert out[2] == "None", raw
        self.assert_tcl_tk_library(out[3:5], out[9:11], out[-3:-1], raw)
        self.assert_pkg_config_path(out[5], out[11], out[-1], raw)
        # self.activate_call(activate_script) runs at this point
        python_exe = self._creator.exe.parent / os.path.basename(sys.executable)
        assert self.norm_path(out[6]) == self.norm_path(python_exe), raw
        assert self.norm_path(out[7]) == self.norm_path(self._creator.dest).replace("\\\\", "\\"), raw
        assert out[8] == self._creator.env_name
        # Some attempts to test the prompt output print more than 1 line.
        # So we need to check if the prompt exists on any of them.
        prompt_text = f"({self._creator.env_name}) "
        assert any(prompt_text in line for line in out[12:-7]), raw

        assert out[-7] == "wrote pydoc_test.html", raw
        content = tmp_path / "pydoc_test.html"
        assert content.exists(), raw
        # post deactivation, same as before
        assert out[-6] == out[0], raw
        assert out[-5] == "None", raw
        assert out[-4] == "None", raw

    def assert_tcl_tk_library(self, before, activated, deactivated, raw) -> None:
        user_values = [os.environ.get("TCL_LIBRARY", "None"), os.environ.get("TK_LIBRARY", "None")]
        venv_values = [self._creator.dest.parent / "tcl", self._creator.dest.parent / "tk"]
        # activation_python creates these folders only for an environment whose interpreter reports tcl
        expected_activated = [str(path) for path in venv_values] if venv_values[0].exists() else user_values
        assert (before, activated, deactivated) == (user_values, expected_activated, user_values), raw

    def assert_pkg_config_path(self, before, activated, deactivated, raw) -> None:
        user_value = os.environ.get("PKG_CONFIG_PATH")
        # comparing entries as paths catches a trailing separator as an extra entry
        assert (before, [self.norm_path(entry) for entry in activated.split(os.pathsep)], deactivated) == (
            str(user_value),
            [
                self.norm_path(self._creator.dest / "lib" / "pkgconfig"),
                *([self.norm_path(user_value)] if user_value else []),
            ],
            str(user_value),
        ), raw

    def quote(self, s):
        return self.of_class.quote(s)

    def python_cmd(self, cmd) -> str:
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
            from ctypes import create_unicode_buffer, windll  # ruff:ignore[import-outside-top-level]

            buffer_cont = create_unicode_buffer(256)
            get_long_path_name = windll.kernel32.GetLongPathNameW
            get_long_path_name(str(path), buffer_cont, 256)
            result = buffer_cont.value or path
        return normcase(result)


class RaiseOnNonSourceCall(ActivationTester):
    def __init__(  # ruff:ignore[too-many-arguments]
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
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
        )
        _out, err_ = process.communicate(timeout=60)
        err = err_.decode("utf-8")
        assert process.returncode
        assert self.non_source_fail_message in err


@pytest.fixture(scope="session")
def activation_tester_class():
    return ActivationTester


@pytest.fixture(scope="session")
def raise_on_non_source_class():
    return RaiseOnNonSourceCall


@pytest.fixture(
    scope="session",
    params=[
        pytest.param((prompt, tcl), id=f"{'with' if prompt else 'no'}_prompt-{'with' if tcl else 'no'}_tcl")
        for prompt in (True, False)
        for tcl in (True, False)
    ],
)
def activation_python(request, tmp_path_factory, special_char_name, current_fastest):
    dest = os.path.join(str(tmp_path_factory.mktemp("activation-tester-env")), special_char_name)
    cmd = ["--without-pip", dest, "--creator", current_fastest, "-vv", "--no-periodic-update"]
    # `params` is accessed here. https://docs.pytest.org/en/stable/reference/reference.html#pytest-fixture
    prompt, tcl = request.param
    if prompt:
        cmd += ["--prompt", special_char_name]
    session = cli_run(cmd)
    if tcl:
        # the interpreter reports tcl_lib only when TCL_LIBRARY is set during its cached probe, so regenerate the scripts
        # with the values patched instead
        with pytest.MonkeyPatch.context() as monkeypatch:
            for name in ("tcl", "tk"):
                (path := Path(dest).parent / name).mkdir()
                monkeypatch.setattr(session.creator.interpreter, f"{name}_lib", str(path))
            for activator in session.activators:
                activator.generate(session.creator)
    pydoc_test = session.creator.purelib / "pydoc_test.py"
    pydoc_test.write_text('"""This is pydoc_test.py"""', encoding="utf-8")
    return session


@pytest.fixture(params=[False, True], ids=["user_env_unset", "user_env_set"])
def activation_tester(request, activation_python, monkeypatch, tmp_path, is_inside_ci):
    for name in ("PKG_CONFIG_PATH", "TCL_LIBRARY", "TK_LIBRARY"):
        if request.param:
            monkeypatch.setenv(name, f"user-{name.lower()}")
        else:
            monkeypatch.delenv(name, raising=False)

    def _tester(tester_class):
        tester = tester_class(activation_python)
        if not tester.of_class.supports(activation_python.creator.interpreter):
            pytest.skip(f"{tester.of_class.__name__} not supported")
        version = tester.get_version(raise_on_fail=is_inside_ci)
        if not isinstance(version, str):
            pytest.skip(reason=str(version))
        return tester(monkeypatch, tmp_path)

    return _tester
