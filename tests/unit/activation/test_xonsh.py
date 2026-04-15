from __future__ import annotations

from argparse import Namespace
from shutil import which

import pytest

from virtualenv.activation import XonshActivator
from virtualenv.info import IS_WIN


@pytest.mark.parametrize(
    ("tcl_lib", "tk_lib", "present"),
    [
        ("/path/to/tcl", "/path/to/tk", True),
        (None, None, False),
    ],
)
def test_xonsh_tkinter_generation(tmp_path, tcl_lib, tk_lib, present):
    # GIVEN
    class MockInterpreter:
        pass

    interpreter = MockInterpreter()
    interpreter.tcl_lib = tcl_lib
    interpreter.tk_lib = tk_lib

    class MockCreator:
        def __init__(self, dest):
            self.dest = dest
            self.bin_dir = dest / ("Scripts" if IS_WIN else "bin")
            self.bin_dir.mkdir()
            self.interpreter = interpreter
            self.pyenv_cfg = {}
            self.env_name = "my-env"

    creator = MockCreator(tmp_path)
    options = Namespace(prompt=None)
    activator = XonshActivator(options)

    # WHEN
    activator.generate(creator)
    content = (creator.bin_dir / "activate.xsh").read_text(encoding="utf-8")

    # THEN: TCL/TK are declared unconditionally in managed_vars so deactivate
    # tears them down whenever they were introduced by an activation.
    assert '"TCL_LIBRARY"' in content
    assert '"TK_LIBRARY"' in content

    if present:
        # The override-loop tuple carries the interpreter paths as Python literals.
        assert '("TCL_LIBRARY", \'/path/to/tcl\')' in content
        assert '("TK_LIBRARY", \'/path/to/tk\')' in content
    else:
        # Without TCL/TK support the override loop sees empty strings (skipped at runtime).
        assert '("TCL_LIBRARY", \'\')' in content
        assert '("TK_LIBRARY", \'\')' in content


def test_xonsh_quote():
    assert XonshActivator.quote("hello") == "'hello'"
    assert XonshActivator.quote("it's") == '"it\'s"'
    assert XonshActivator.quote("") == "''"


@pytest.mark.skipif(which("xonsh") is None, reason="xonsh is not installed")
def test_xonsh(activation_tester_class, activation_tester):
    class Xonsh(activation_tester_class):
        def __init__(self, session) -> None:
            super().__init__(XonshActivator, session, "xonsh", "activate.xsh", "xsh")
            self._invoke_script = ["xonsh", "--no-rc"]

        def env(self, tmp_path):
            env = super().env(tmp_path)
            # make xonsh skip xontrib auto-loading to avoid third-party noise
            env["XONSH_NO_AMALGAMATE"] = "1"
            env["XONSH_SHOW_TRACEBACK"] = "1"
            return env

        def print_prompt(self):
            return 'echo @("(" + $VIRTUAL_ENV_PROMPT + ") ")'

        def activate_call(self, script):
            return f"source {self.quote(str(script))}"

    activation_tester(Xonsh)
