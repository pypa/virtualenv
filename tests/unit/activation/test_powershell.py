from __future__ import annotations

import sys

import pytest

from virtualenv.activation import PowerShellActivator


@pytest.mark.slow
def test_powershell(activation_tester_class, activation_tester, monkeypatch):
    monkeypatch.setenv("TERM", "xterm")

    class PowerShell(activation_tester_class):
        def __init__(self, session) -> None:
            cmd = "powershell.exe" if sys.platform == "win32" else "pwsh"
            super().__init__(PowerShellActivator, session, cmd, "activate.ps1", "ps1")
            self._version_cmd = [cmd, "-c", "$PSVersionTable"]
            self._invoke_script = [cmd, "-ExecutionPolicy", "ByPass", "-File"]
            self.activate_cmd = "."
            self.script_encoding = "utf-8-sig"

        def _get_test_lines(self, activate_script):
            lines = super()._get_test_lines(activate_script)
            lines.insert(3, self.print_os_env_var("PKG_CONFIG_PATH"))
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

        def invoke_script(self):
            return [self.cmd, "-File"]

        def print_prompt(self):
            return "prompt"

        def quote(self, s):
            """
            Tester will pass strings to native commands on Windows so extra
            parsing rules are used. Check `PowerShellActivator.quote` for more
            details.
            """
            text = PowerShellActivator.quote(s)
            return text.replace('"', '""') if sys.platform == "win32" else text

        def activate_call(self, script):
            # Commands are called without quotes in PowerShell
            cmd = self.activate_cmd
            scr = self.quote(str(script))
            return f"{cmd} {scr}".strip()

    activation_tester(PowerShell)
