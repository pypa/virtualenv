from __future__ import annotations

import pytest

from virtualenv.activation import BatchActivator


@pytest.mark.usefixtures("activation_python")
def test_batch(activation_tester_class, activation_tester, tmp_path):
    version_script = tmp_path / "version.bat"
    version_script.write_text("ver", encoding="utf-8")

    class Batch(activation_tester_class):
        def __init__(self, session) -> None:
            super().__init__(BatchActivator, session, None, "activate.bat", "bat")
            self._version_cmd = [str(version_script)]
            self._invoke_script = []
            self.deactivate = "call deactivate"
            self.activate_cmd = "call"
            self.pydoc_call = f"call {self.pydoc_call}"
            self.unix_line_ending = False

        def _get_test_lines(self, activate_script):
            lines = ["@echo off", *super()._get_test_lines(activate_script)]
            lines.insert(4, self.print_os_env_var("PKG_CONFIG_PATH"))
            i = next(i for i, line in enumerate(lines) if "pydoc" in line)
            lines.insert(i, self.print_os_env_var("PKG_CONFIG_PATH"))
            lines.insert(-1, self.print_os_env_var("PKG_CONFIG_PATH"))
            return lines

        def assert_output(self, out, raw, tmp_path):
            assert out[3] == "None"

            pkg_config_path = self.norm_path(self._creator.dest / "lib" / "pkgconfig")
            assert self.norm_path(out[9]) == pkg_config_path

            assert out[-2] == "None"
            super().assert_output(out[:3] + out[4:9] + out[10:-2] + [out[-1]], raw, tmp_path)

        def quote(self, s):
            if '"' in s or " " in s:
                text = s.replace('"', r"\"")
                return f'"{text}"'
            return s

        def print_prompt(self):
            return 'echo "%PROMPT%"'

    activation_tester(Batch)


@pytest.mark.usefixtures("activation_python")
def test_batch_output(activation_tester_class, activation_tester, tmp_path):
    version_script = tmp_path / "version.bat"
    version_script.write_text("ver", encoding="utf-8")

    class Batch(activation_tester_class):
        def __init__(self, session) -> None:
            super().__init__(BatchActivator, session, None, "activate.bat", "bat")
            self._version_cmd = [str(version_script)]
            self._invoke_script = []
            self.deactivate = "call deactivate"
            self.activate_cmd = "call"
            self.pydoc_call = f"call {self.pydoc_call}"
            self.unix_line_ending = False

        def _get_test_lines(self, activate_script):
            """
            Build intermediary script which will be then called.
            In the script just activate environment, call echo to get current
            echo setting, and then deactivate. This ensures that echo setting
            is preserved and no unwanted output appears.
            """
            intermediary_script_path = str(tmp_path / "intermediary.bat")
            activate_script_quoted = self.quote(str(activate_script))
            return [
                "@echo on",
                f"@echo @call {activate_script_quoted} > {intermediary_script_path}",
                f"@echo @echo >> {intermediary_script_path}",
                f"@echo @deactivate >> {intermediary_script_path}",
                f"@call {intermediary_script_path}",
            ]

        def assert_output(self, out, raw, tmp_path):  # noqa: ARG002
            assert out[0] == "ECHO is on.", raw

        def quote(self, s):
            if '"' in s or " " in s:
                text = s.replace('"', r"\"")
                return f'"{text}"'
            return s

        def print_prompt(self):
            return 'echo "%PROMPT%"'

    activation_tester(Batch)
