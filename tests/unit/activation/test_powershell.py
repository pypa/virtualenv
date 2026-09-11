from __future__ import annotations

import shutil
import subprocess
import sys
from argparse import Namespace

import pytest

from virtualenv.activation import PowerShellActivator


def test_powershell_pydoc_call_operator(tmp_path) -> None:
    """Test that PowerShell pydoc function uses call operator to handle spaces in python path."""

    # GIVEN: A mock interpreter
    class MockInterpreter:
        os = "nt"
        tcl_lib = None
        tk_lib = None

    class MockCreator:
        def __init__(self, dest) -> None:
            self.dest = dest
            self.bin_dir = dest / "Scripts"
            self.bin_dir.mkdir(parents=True)
            self.interpreter = MockInterpreter()
            self.pyenv_cfg = {}
            self.env_name = "test-env"

    creator = MockCreator(tmp_path)
    options = Namespace(prompt=None)
    activator = PowerShellActivator(options)

    # WHEN: Generate activation scripts
    activator.generate(creator)

    # THEN: pydoc function should use call operator & to handle paths with spaces
    activate_content = (creator.bin_dir / "activate.ps1").read_text(encoding="utf-8-sig")

    # The pydoc function should use & call operator to handle paths with spaces
    assert "& python -m pydoc" in activate_content, (
        f"pydoc function should use & call operator. Content:\n{activate_content}"
    )


@pytest.mark.parametrize(
    ("tcl_lib", "tk_lib", "present"),
    [
        ("C:\\tcl", "C:\\tk", True),
        (None, None, False),
    ],
)
def test_powershell_tkinter_generation(tmp_path, tcl_lib, tk_lib, present) -> None:
    # GIVEN
    class MockInterpreter:
        os = "nt"

    interpreter = MockInterpreter()
    interpreter.tcl_lib = tcl_lib
    interpreter.tk_lib = tk_lib

    class MockCreator:
        def __init__(self, dest) -> None:
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
    # PKG_CONFIG_PATH is always set
    assert "New-Variable -Scope global -Name _OLD_PKG_CONFIG_PATH" in content
    assert '$env:PKG_CONFIG_PATH = "$env:VIRTUAL_ENV\\lib\\pkgconfig;$env:PKG_CONFIG_PATH"' in content
    assert "if (Test-Path variable:_OLD_PKG_CONFIG_PATH)" in content
    assert "$env:PKG_CONFIG_PATH = $variable:_OLD_PKG_CONFIG_PATH" in content
    assert 'Remove-Variable "_OLD_PKG_CONFIG_PATH" -Scope global' in content

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
def test_powershell(activation_tester_class, activation_tester, monkeypatch) -> None:
    monkeypatch.setenv("TERM", "xterm")

    class PowerShell(activation_tester_class):
        def __init__(self, session) -> None:
            cmd = "pwsh" if shutil.which("pwsh") else "powershell.exe" if sys.platform == "win32" else "pwsh"
            super().__init__(PowerShellActivator, session, cmd, "activate.ps1", "ps1")
            self._version_cmd = [cmd, "-c", "$PSVersionTable"]
            self._invoke_script = [cmd, "-NonInteractive", "-NoProfile", "-ExecutionPolicy", "ByPass", "-File"]
            self.activate_cmd = "."
            self.script_encoding = "utf-8-sig"

        def _get_test_lines(self, activate_script):
            return super()._get_test_lines(activate_script)

        def invoke_script(self):
            return [self.cmd, "-File"]

        def print_os_env_var(self, var) -> str:
            return f'if ($env:{var} -eq $null) {{ "None" }} else {{ $env:{var} }}'

        def print_prompt(self) -> str:
            return "prompt"

        def quote(self, s):
            """Tester will pass strings to native commands on Windows so extra parsing rules are used. Check `PowerShellActivator.quote` for more details."""
            text = PowerShellActivator.quote(s)
            return text.replace('"', '""') if sys.platform == "win32" else text

        def activate_call(self, script):
            # Commands are called without quotes in PowerShell
            cmd = self.activate_cmd
            scr = self.quote(str(script))
            return f"{cmd} {scr}".strip()

    activation_tester(PowerShell)


@pytest.mark.parametrize("venv_sets_tcl", [True, False])
@pytest.mark.parametrize("was_set", [True, False])
def test_powershell_deactivate_restores_tcl_tk_library(tmp_path, venv_sets_tcl, was_set) -> None:
    powershell = shutil.which("pwsh") or (shutil.which("powershell.exe") if sys.platform == "win32" else None)
    if powershell is None:
        pytest.skip("powershell is not installed")

    class MockInterpreter:
        os = "nt"

    interpreter = MockInterpreter()
    interpreter.tcl_lib = str(tmp_path / "venv-tcl") if venv_sets_tcl else None
    interpreter.tk_lib = str(tmp_path / "venv-tk") if venv_sets_tcl else None

    class MockCreator:
        def __init__(self, dest) -> None:
            self.dest = dest
            self.bin_dir = dest / "Scripts"
            self.bin_dir.mkdir(parents=True)
            self.interpreter = interpreter
            self.pyenv_cfg = {}
            self.env_name = "env"

    creator = MockCreator(tmp_path / "env")
    (creator.dest / "pyvenv.cfg").write_text("", encoding="utf-8")
    PowerShellActivator(Namespace(prompt=None)).generate(creator)

    setup = "$env:TCL_LIBRARY = 'user-tcl'; $env:TK_LIBRARY = 'user-tk'" if was_set else ""
    show = 'if ($env:{0} -eq $null) {{ "None" }} else {{ $env:{0} }}'
    show_both = f"{show.format('TCL_LIBRARY')}\n{show.format('TK_LIBRARY')}"
    driver = tmp_path / "driver.ps1"
    driver.write_text(
        f"Remove-Item env:TCL_LIBRARY, env:TK_LIBRARY -ErrorAction SilentlyContinue\n{setup}\n"
        f". '{creator.bin_dir / 'activate.ps1'}'\n{show_both}\ndeactivate\n{show_both}\n",
        encoding="utf-8-sig",
    )
    out = subprocess.run(
        [powershell, "-NonInteractive", "-NoProfile", "-ExecutionPolicy", "ByPass", "-File", str(driver)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
        check=True,
    ).stdout

    before = ["user-tcl", "user-tk"] if was_set else ["None", "None"]
    activated = [interpreter.tcl_lib, interpreter.tk_lib] if venv_sets_tcl else before
    # activation must not drop a value it does not replace, and deactivate puts back what was there
    assert out.splitlines() == [*activated, *before], out
