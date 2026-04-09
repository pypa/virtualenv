from __future__ import annotations

import subprocess
from argparse import Namespace
from shutil import which
from typing import TYPE_CHECKING

import pytest

from virtualenv.activation import NushellActivator
from virtualenv.info import IS_WIN
from virtualenv.run import cli_run

if TYPE_CHECKING:
    from pathlib import Path


def test_nushell_tkinter_generation(tmp_path) -> None:
    # GIVEN
    class MockInterpreter:
        pass

    interpreter = MockInterpreter()
    interpreter.tcl_lib = "/path/to/tcl"
    interpreter.tk_lib = "/path/to/tk"
    quoted_tcl_path = NushellActivator.quote(interpreter.tcl_lib)
    quoted_tk_path = NushellActivator.quote(interpreter.tk_lib)

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
    activator = NushellActivator(options)

    # WHEN
    activator.generate(creator)
    content = (creator.bin_dir / "activate.nu").read_text(encoding="utf-8")

    # THEN
    # PKG_CONFIG_PATH is always set
    assert "let old_pkg_config_path = if (has-env 'PKG_CONFIG_PATH')" in content
    assert "let new_pkg_config_path = " in content
    assert "PKG_CONFIG_PATH: $new_pkg_config_path" in content

    expected_tcl = f"let $new_env = $new_env | insert TCL_LIBRARY {quoted_tcl_path}"
    expected_tk = f"let $new_env = $new_env | insert TK_LIBRARY {quoted_tk_path}"

    assert expected_tcl in content
    assert expected_tk in content

    # overlay hide is a parser keyword: a def body would fail at parse time because the overlay doesn't exist yet
    # when the def is compiled. The alias defers that check to call time, when the overlay is active.
    assert "export alias deactivate = overlay hide activate" in content
    # nushell shows one line of context before the error site, so placing the hint comment directly above the alias
    # makes it appear in the error output users see when they activate via `use *` or a custom name (gh-3103).
    lines = content.splitlines()
    alias_idx = next(i for i, line in enumerate(lines) if "export alias deactivate" in line)
    assert alias_idx > 0
    assert "overlay use activate.nu" in lines[alias_idx - 1]


def test_nushell(activation_tester_class, activation_tester) -> None:
    class Nushell(activation_tester_class):
        def __init__(self, session) -> None:
            super().__init__(NushellActivator, session, which("nu"), "activate.nu", "nu")

            self.activate_cmd = "overlay use"
            self.unix_line_ending = not IS_WIN

        def print_prompt(self) -> str:
            return r"print $env.VIRTUAL_PREFIX"

        def activate_call(self, script):
            # Commands are called without quotes in Nushell
            cmd = self.activate_cmd
            scr = self.quote(str(script))
            return f"{cmd} {scr}".strip()

    activation_tester(Nushell)


def test_nushell_deactivate_errors(tmp_path: Path) -> None:
    """Regression for gh-3103: both misuse patterns give actionable inline errors.

    `^nu | complete` captures stderr from child invocations without aborting the
    outer script, so both cases run in a single subprocess call.
    """
    nu = which("nu")
    if nu is None:
        pytest.skip("nu not installed")

    activate_nu = cli_run(["--without-pip", str(tmp_path / "venv")]).creator.bin_dir / "activate.nu"
    quoted = NushellActivator.quote(str(activate_nu))

    # `to nuon` re-quotes the path so it remains valid nushell syntax after string interpolation.
    script = f"""\
let path = {quoted}
let r1 = (^nu --commands $"use ($path | to nuon) *; deactivate" | complete)
if ($r1.exit_code == 0) {{ error make {{ msg: "expected deactivate to fail for use-star" }} }}
if not ("not an active overlay" in $r1.stderr) {{ error make {{ msg: "overlay error missing" }} }}
if not ("overlay use activate.nu" in $r1.stderr) {{ error make {{ msg: "hint missing for use-star" }} }}
let r2 = (^nu --commands $"overlay use ($path | to nuon) as myenv; deactivate" | complete)
if ($r2.exit_code == 0) {{ error make {{ msg: "expected deactivate to fail for custom name" }} }}
if not ("not an active overlay" in $r2.stderr) {{ error make {{ msg: "overlay error missing" }} }}
if not ("overlay hide NAME" in $r2.stderr) {{ error make {{ msg: "hint missing for custom name" }} }}
"""
    result = subprocess.run([nu, "--commands", script], capture_output=True, text=True, timeout=60, check=False)
    assert result.returncode == 0, result.stderr
