from __future__ import annotations

from argparse import Namespace
from shutil import which

from virtualenv.activation import NushellActivator
from virtualenv.info import IS_WIN


def test_nushell_tkinter_generation(tmp_path):
    # GIVEN
    class MockInterpreter:
        pass

    interpreter = MockInterpreter()
    interpreter.tcl_lib = "/path/to/tcl"
    interpreter.tk_lib = "/path/to/tk"
    quoted_tcl_path = NushellActivator.quote(interpreter.tcl_lib)
    quoted_tk_path = NushellActivator.quote(interpreter.tk_lib)

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
    activator = NushellActivator(options)

    # WHEN
    activator.generate(creator)
    content = (creator.bin_dir / "activate.nu").read_text(encoding="utf-8")

    # THEN
    expected_tcl = f"let $new_env = $new_env | insert TCL_LIBRARY {quoted_tcl_path}"
    expected_tk = f"let $new_env = $new_env | insert TK_LIBRARY {quoted_tk_path}"

    assert expected_tcl in content
    assert expected_tk in content


def test_nushell(activation_tester_class, activation_tester):
    class Nushell(activation_tester_class):
        def __init__(self, session) -> None:
            cmd = which("nu")
            if cmd is None and IS_WIN:
                cmd = "c:\\program files\\nu\\bin\\nu.exe"

            super().__init__(NushellActivator, session, cmd, "activate.nu", "nu")

            self.activate_cmd = "overlay use"
            self.unix_line_ending = not IS_WIN

        def print_prompt(self):
            return r"print $env.VIRTUAL_PREFIX"

        def activate_call(self, script):
            # Commands are called without quotes in Nushell
            cmd = self.activate_cmd
            scr = self.quote(str(script))
            return f"{cmd} {scr}".strip()

    activation_tester(Nushell)
