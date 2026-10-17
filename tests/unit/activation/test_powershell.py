from __future__ import annotations

import os
import shutil
import subprocess
import sys
from argparse import Namespace
from typing import TYPE_CHECKING, Final

import pytest

from virtualenv.activation import PowerShellActivator
from virtualenv.info import IS_WIN
from virtualenv.run import cli_run

if TYPE_CHECKING:
    from pathlib import Path


_POWERSHELLS: Final = [path for name in ("pwsh", "powershell.exe") if (path := shutil.which(name))]


@pytest.mark.parametrize("powershell", _POWERSHELLS)
@pytest.mark.parametrize(
    ("name", "mode"),
    [
        pytest.param(name, mode, id=f"{mode}-{label}", marks=marks)
        for name, label, marks in (
            ("ordinary", "ordinary", []),
            ("env[one]", "brackets", []),
            ("env\\one", "backslash", [pytest.mark.skipif(IS_WIN, reason="POSIX filename")]),
        )
        for mode in ("implicit", "relative", "drive", "provider", "home")
    ],
)
@pytest.mark.parametrize("configured_prompt", [pytest.param(None, id="name"), pytest.param("custom", id="config")])
def test_powershell_literal_destination(
    tmp_path: Path, name: str, configured_prompt: str | None, mode: str, powershell: str
) -> None:
    dest: Final = os.path.join(str(tmp_path), name)
    args: Final = ["--without-pip", "--no-periodic-update", "--activators", "powershell", dest]
    if configured_prompt is not None:
        args.extend(["--prompt", configured_prompt])
    # Simulated-platform tests change pathlib's separators at collection, so create the environment in a fresh process.
    subprocess.run([sys.executable, "-m", "virtualenv", *args], capture_output=True, check=True)
    venv_dir: Final = {
        "implicit": None,
        "relative": name,
        "drive": f"ReviewEnv:/{name}",
        "provider": f"FileSystem::{dest}",
        "home": f"~/{os.path.relpath(dest, os.path.expanduser('~'))}",
    }[mode]
    activate = f". {PowerShellActivator.quote(os.path.join(dest, 'Scripts' if IS_WIN else 'bin', 'activate.ps1'))}"
    if venv_dir is not None:
        activate += f" -VenvDir {PowerShellActivator.quote(venv_dir)}"
    lines: Final = [activate, 'Write-Output "$env:VIRTUAL_ENV|$env:VIRTUAL_ENV_PROMPT"', ""]
    if mode == "drive":
        drive_root = PowerShellActivator.quote(str(tmp_path))
        lines.insert(0, f"New-PSDrive -Name ReviewEnv -PSProvider FileSystem -Root {drive_root} | Out-Null")
    driver: Final = tmp_path / "driver.ps1"
    driver.write_text("\n".join(lines), encoding="utf-8-sig")
    result: Final = subprocess.run(
        [powershell, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", str(driver)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=tmp_path,
        timeout=120,
        check=True,
    )
    assert (result.stdout.strip(), result.stderr) == (f"{dest}|{configured_prompt or name}", "")


@pytest.mark.parametrize("powershell", _POWERSHELLS)
def test_powershell_reports_missing_config(tmp_path: Path, current_fastest: str, powershell: str) -> None:
    session: Final = cli_run([
        "--without-pip",
        "--no-periodic-update",
        "--activators",
        "powershell",
        "--creator",
        current_fastest,
        str(tmp_path / "env"),
    ])
    (session.creator.dest / "pyvenv.cfg").unlink()
    result: Final = subprocess.run(
        [
            powershell,
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(session.creator.bin_dir / "activate.ps1"),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
        check=True,
    )
    assert "Cannot find configuration file" in result.stderr


@pytest.mark.skipif(shutil.which("pwsh") is None, reason="requires PowerShell Core")
@pytest.mark.parametrize(
    "delimiter",
    [
        pytest.param(chr(0x27), id="apostrophe"),
        pytest.param(chr(0x2018), id="left-single"),
        pytest.param(chr(0x2019), id="right-single"),
        pytest.param(chr(0x201A), id="low-9"),
        pytest.param(chr(0x201B), id="high-reversed-9"),
    ],
)
def test_powershell_quote_neutralizes_single_quote_delimiters(tmp_path: Path, delimiter: str) -> None:
    marker = tmp_path / "PWNED"
    payload = f"x{delimiter}+$(New-Item -ItemType File -Path '{marker}')+{delimiter}y"
    literal = PowerShellActivator.quote(payload)
    result = subprocess.run(
        ["pwsh", "-NoProfile", "-NonInteractive", "-Command", f"Write-Output {literal}"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )

    assert (marker.exists(), result.stdout.strip()) == (False, payload), result.stderr


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
    assert '$env:PKG_CONFIG_PATH = [IO.Path]::Combine($env:VIRTUAL_ENV, "lib", "pkgconfig")' in content
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

        def print_state(self, names: tuple[str, ...]) -> str:
            lookups = (f'if ($env:{var} -eq $null) {{ "None" }} else {{ $env:{var} }}' for var in names)
            return "; ".join([self.print_python_exe(), *lookups])

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


@pytest.mark.parametrize("powershell", _POWERSHELLS)
def test_powershell_rejects_non_filesystem_drive(tmp_path: Path, powershell: str) -> None:
    session: Final = cli_run([str(tmp_path / "env"), "--no-seed", "--activators", "powershell"])
    result: Final = subprocess.run(
        [
            powershell,
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            (
                f". {PowerShellActivator.quote(str(session.creator.bin_dir / 'activate.ps1'))} -VenvDir 'Env:/x'; "
                "Write-Output $env:VIRTUAL_ENV"
            ),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
        check=False,
    )
    assert (result.returncode, result.stdout, "Cannot resolve environment directory 'Env:/x'" in result.stderr) == (
        1,
        "",
        True,
    ), result.stderr


@pytest.mark.skipif(not IS_WIN, reason="Windows registry provider")
@pytest.mark.parametrize("powershell", _POWERSHELLS)
def test_powershell_home_from_registry(tmp_path: Path, powershell: str) -> None:
    session: Final = cli_run([str(tmp_path / "env"), "--no-seed", "--activators", "powershell"])
    result: Final = subprocess.run(
        [
            powershell,
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            f"Set-Location HKCU:\\; . {PowerShellActivator.quote(str(session.creator.bin_dir / 'activate.ps1'))} -VenvDir '~'; Write-Output $env:VIRTUAL_ENV",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
        check=True,
    )
    assert result.stdout.strip() == os.path.expanduser("~")
