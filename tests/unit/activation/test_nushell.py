from __future__ import annotations

import subprocess
from argparse import Namespace
from shutil import which

import pytest

from virtualenv.activation import NushellActivator
from virtualenv.info import IS_WIN


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

    # overlay hide is a parser keyword: using it in a def body causes a parse-time
    # error because the overlay doesn't exist yet when the def is compiled.
    # The alias defers that check to call time, when the overlay is active.
    assert "export alias deactivate = overlay hide activate" in content
    # nushell shows one line of context before the error site, so placing the
    # hint comment directly above the alias makes it appear in the error output
    # users see when they activate via `use *` or a custom name (gh-3103).
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

    result = activation_tester(Nushell)
    if result is None:
        return  # activation failed with CalledProcessError, already asserted

    # Regression for gh-3103: nushell shows one line of context before the error site, so
    # the hint comment placed directly above the alias surfaces in both error cases below.
    _env, activate_script = result
    nu = which("nu")
    if nu is None:
        pytest.skip("nu not installed")
    quoted = NushellActivator.quote(str(activate_script))

    # `use ... *` imports exports without creating an overlay, so deactivate's
    # `overlay hide activate` finds nothing and errors; the hint should tell the user
    # to re-activate with `overlay use`.
    proc = subprocess.run(
        [nu, "--commands", f"use {quoted} *; deactivate"],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert proc.returncode != 0
    assert "not an active overlay" in proc.stderr
    assert "overlay use activate.nu" in proc.stderr

    # `overlay use ... as NAME` creates an overlay named NAME, not "activate", so
    # deactivate errors; the hint should tell the user to run `overlay hide NAME` directly.
    proc = subprocess.run(
        [nu, "--commands", f"overlay use {quoted} as myenv; deactivate"],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert proc.returncode != 0
    assert "not an active overlay" in proc.stderr
    assert "overlay hide NAME" in proc.stderr
