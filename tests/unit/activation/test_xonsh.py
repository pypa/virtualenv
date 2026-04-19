from __future__ import annotations

from argparse import Namespace
from shutil import which
from unittest.mock import create_autospec

import pytest
from python_discovery import PythonInfo

from virtualenv.activation import XonshActivator
from virtualenv.create.creator import Creator


@pytest.mark.parametrize(
    ("tcl_lib", "tk_lib", "present"),
    [
        ("/path/to/tcl", "/path/to/tk", True),
        (None, None, False),
    ],
)
def test_xonsh_tkinter_generation(tmp_path, tcl_lib, tk_lib, present) -> None:
    # GIVEN
    interpreter = create_autospec(PythonInfo, instance=True)
    interpreter.tcl_lib = tcl_lib
    interpreter.tk_lib = tk_lib

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()

    creator = create_autospec(Creator, instance=True)
    creator.dest = tmp_path
    creator.bin_dir = bin_dir
    creator.interpreter = interpreter
    creator.pyenv_cfg = {}
    creator.env_name = "my-env"

    activator = XonshActivator(Namespace(prompt=None))

    # WHEN
    activator.generate(creator)
    content = (bin_dir / "activate.xsh").read_text(encoding="utf-8")

    # THEN
    # `managed_vars` always lists TCL_LIBRARY/TK_LIBRARY so deactivate can clean up
    # whatever activation introduced — regardless of whether the interpreter reported
    # tcl_lib/tk_lib.
    assert '"TCL_LIBRARY"' in content
    assert '"TK_LIBRARY"' in content

    if present:
        # Paths are embedded in __init__ as Python string literals and used
        # from self.embedded_* attributes during activate().
        assert "self.embedded_tcl_library = '/path/to/tcl'" in content
        assert "self.embedded_tk_library = '/path/to/tk'" in content
    else:
        # Empty strings are falsy, so the override loop is skipped at runtime.
        assert "self.embedded_tcl_library = ''" in content
        assert "self.embedded_tk_library = ''" in content


def test_xonsh_quote() -> None:
    # XonshActivator.quote uses repr() so the template substitution produces valid
    # Python literals — this is what the rest of the tests rely on.
    assert XonshActivator.quote("hello") == "'hello'"
    assert XonshActivator.quote("it's") == '"it\'s"'
    assert XonshActivator.quote("") == "''"


@pytest.mark.skipif(which("xonsh") is None, reason="xonsh is not installed")
def test_xonsh(activation_tester_class, activation_tester) -> None:
    class Xonsh(activation_tester_class):
        def __init__(self, session) -> None:
            super().__init__(XonshActivator, session, "xonsh", "activate.xsh", "xsh")
            self._invoke_script.append("--no-rc")

        def env(self, tmp_path):
            env = super().env(tmp_path)
            # Keep the subprocess hermetic: skip auto-loaded xontribs that a dev may
            # have installed locally, and surface tracebacks so test failures are
            # actionable.
            env["XONTRIBS_AUTOLOAD_DISABLED"] = "1"
            env["XONSH_SHOW_TRACEBACK"] = "1"
            return env

        def print_prompt(self):
            return 'echo @("(" + $VIRTUAL_ENV_PROMPT + ") ")'

        def activate_call(self, script):
            return f"source {self.quote(str(script))}"

    activation_tester(Xonsh)
