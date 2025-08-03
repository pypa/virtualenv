from __future__ import annotations

import sys
from argparse import Namespace

import pytest

from virtualenv.activation import PowerShellActivator


@pytest.mark.parametrize(
    ("tcl_lib", "tk_lib", "present"),
    [
        ("C:\\tcl", "C:\\tk", True),
        (None, None, False),
    ],
)
def test_powershell_tkinter_generation(tmp_path, tcl_lib, tk_lib, present):
    # GIVEN
    class MockInterpreter:
        os = "nt"

    interpreter = MockInterpreter()
    interpreter.tcl_lib = tcl_lib
    interpreter.tk_lib = tk_lib

    class MockCreator:
        def __init__(self, dest):
            self.dest = dest
            self.bin_dir = dest / "bin"
            self.bin_dir.mkdir()
            self.interpreter = interpreter
            self.pyenv_cfg = {}
            self.env_name = "my-env"

    creator = MockCreator(tmp_path)
    options = Namespace(prompt=None)
    activator = PowerShellActivator(options)

    # WHEN
    activator.generate(creator)
    content = (creator.bin_dir / "activate.ps1").read_text(encoding="utf-8-sig")

    # THEN
    if present:
        assert "if ('C:\\tcl' -ne \"\")" in content
        assert "$env:TCL_LIBRARY = 'C:\\tcl'" in content
        assert "if ('C:\\tk' -ne \"\")" in content
        assert "$env:TK_LIBRARY = 'C:\\tk'" in content
        assert "if (Test-Path variable:_OLD_VIRTUAL_TCL_LIBRARY)" in content
        assert "if (Test-Path variable:_OLD_VIRTUAL_TK_LIBRARY)" in content
    else:
        assert "if ('' -ne \"\")" in content
        assert "$env:TCL_LIBRARY = ''" in content


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
