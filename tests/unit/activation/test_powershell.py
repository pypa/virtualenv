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
            return super()._get_test_lines(activate_script)

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


@pytest.mark.skipif(sys.platform != "win32", reason="UNC paths are a Windows feature")
def test_powershell_unc_path(activation_tester_class, activation_tester, monkeypatch, tmp_path):
    monkeypatch.setenv("TERM", "xterm")

    # Create a fake UNC path by creating a temporary directory
    # and then accessing it via the \\localhost\c$\... path
    unc_path = str(tmp_path).replace("C:", r"\\localhost\C$")
    unc_path_venv = f"{unc_path}\\.venv"

    class PowerShellUNC(activation_tester_class):
        def __init__(self, session) -> None:
            cmd = "powershell.exe"
            super().__init__(PowerShellActivator, session, cmd, "activate.ps1", "ps1", venv_name=".venv")
            self.venv_dir = unc_path_venv
            self._version_cmd = [cmd, "-c", "$PSVersionTable"]
            self._invoke_script = [cmd, "-ExecutionPolicy", "ByPass", "-File"]
            self.activate_cmd = "."
            self.script_encoding = "utf-8-sig"

        def _get_test_lines(self, activate_script):
            return super()._get_test_lines(activate_script)

        def invoke_script(self):
            return [self.cmd, "-File"]

        def print_prompt(self):
            return "prompt"

        def quote(self, s):
            text = PowerShellActivator.quote(s)
            return text.replace('"', '""')

        def activate_call(self, script):
            cmd = self.activate_cmd
            scr = self.quote(str(script))
            return f"{cmd} {scr}".strip()

    activation_tester(PowerShellUNC)
