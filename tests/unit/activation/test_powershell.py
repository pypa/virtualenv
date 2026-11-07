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


_POWERSHELLS: Final[list[str]] = [path for name in ("pwsh", "powershell.exe") if (path := shutil.which(name))]
_VENV_BIN_DIR: Final[str] = "Scripts" if IS_WIN else "bin"


@pytest.mark.parametrize("powershell", _POWERSHELLS)
def test_powershell_clears_pythonhome(tmp_path: Path, powershell: str) -> None:
    session = cli_run(["--no-seed", "--activators", "powershell", str(tmp_path / "env")])
    inherited = str(tmp_path / "missing-pythonhome")
    activate = PowerShellActivator.quote(str(session.creator.bin_dir / "activate.ps1"))
    driver = tmp_path / "pythonhome.ps1"
    driver.write_text(
        f". {activate}\nWrite-Output (Test-Path env:PYTHONHOME)\npython -c 'import sys; print(sys.prefix)'\n"
        "deactivate\nWrite-Output $env:PYTHONHOME\n",
        encoding="utf-8-sig",
    )
    result = subprocess.run(
        [powershell, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", str(driver)],
        env={key: value for key, value in os.environ.items() if key != "COVERAGE_PROCESS_START"}
        | {"PYTHONHOME": inherited},
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
        check=False,
    )

    assert (result.returncode, result.stdout.splitlines(), result.stderr) == (
        0,
        ["False", str(session.creator.dest), inherited],
        "",
    )


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
    prompt_args: Final = {None: [], "custom": ["--prompt", "custom"]}[configured_prompt]
    args: Final = ["--without-pip", "--no-periodic-update", "--activators", "powershell", dest, *prompt_args]
    # Simulated-platform tests change pathlib's separators at collection, so create the environment in a fresh process.
    subprocess.run([sys.executable, "-m", "virtualenv", *args], capture_output=True, check=True)
    venv_args: Final = {
        "implicit": [],
        "relative": ["-VenvDir", PowerShellActivator.quote(name)],
        "drive": ["-VenvDir", PowerShellActivator.quote(f"ReviewEnv:/{name}")],
        "provider": ["-VenvDir", PowerShellActivator.quote(f"FileSystem::{dest}")],
        "home": ["-VenvDir", PowerShellActivator.quote(f"~/{os.path.relpath(dest, os.path.expanduser('~'))}")],
    }[mode]
    activate: Final = " ".join([
        f". {PowerShellActivator.quote(os.path.join(dest, _VENV_BIN_DIR, 'activate.ps1'))}",
        *venv_args,
    ])
    drive_root: Final = PowerShellActivator.quote(str(tmp_path))
    drive_lines: Final = {
        "drive": [f"New-PSDrive -Name ReviewEnv -PSProvider FileSystem -Root {drive_root} | Out-Null"],
    }.get(mode, [])
    lines: Final = [*drive_lines, activate, 'Write-Output "$env:VIRTUAL_ENV|$env:VIRTUAL_ENV_PROMPT"', ""]
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
    # Test that PowerShell pydoc function uses call operator to handle spaces in python path.
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
    activator = PowerShellActivator(Namespace(prompt=None))

    # WHEN: Generate activation scripts
    activator.generate(creator)

    # THEN: pydoc function should use call operator & to handle paths with spaces
    activate_content = (creator.bin_dir / "activate.ps1").read_text(encoding="utf-8-sig")

    # The pydoc function should use & call operator to handle paths with spaces
    assert "& python -m pydoc" in activate_content, (
        f"pydoc function should use & call operator. Content:\n{activate_content}"
    )


@pytest.mark.parametrize(
    ("tcl_lib", "tk_lib", "expected_lines"),
    [
        pytest.param(
            "C:\\tcl",
            "C:\\tk",
            [
                "if ('C:\\tcl' -ne \"\")",
                "$env:TCL_LIBRARY = 'C:\\tcl'",
                "if ('C:\\tk' -ne \"\")",
                "$env:TK_LIBRARY = 'C:\\tk'",
                "if (Test-Path variable:_OLD_VIRTUAL_TCL_LIBRARY)",
                "if (Test-Path variable:_OLD_VIRTUAL_TK_LIBRARY)",
            ],
            id="windows",
        ),
        pytest.param(None, None, ["if ('' -ne \"\")", "$env:TCL_LIBRARY = ''"], id="missing"),
    ],
)
def test_powershell_tkinter_generation(tmp_path, tcl_lib, tk_lib, expected_lines) -> None:
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
    activator = PowerShellActivator(Namespace(prompt=None))

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
    assert [line for line in expected_lines if line not in content] == []


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

        def activate_call(self, script):
            # Commands are called without quotes in PowerShell
            return f"{self.activate_cmd} {self.quote(str(script))}".strip()

        def quote(self, string):
            # Tester will pass strings to native commands on Windows so extra parsing rules are used. Check
            # `PowerShellActivator.quote` for more details.
            text = PowerShellActivator.quote(string)
            return text.replace('"', '""') if sys.platform == "win32" else text

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
