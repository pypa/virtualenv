from __future__ import annotations

from argparse import Namespace

import pytest

from virtualenv.activation import BashActivator
from virtualenv.info import IS_WIN


@pytest.mark.skipif(IS_WIN, reason="Github Actions ships with WSL bash")
@pytest.mark.parametrize(
    ("tcl_lib", "tk_lib", "present"),
    [
        ("/path/to/tcl", "/path/to/tk", True),
        (None, None, False),
    ],
)
def test_bash_tkinter_generation(tmp_path, tcl_lib, tk_lib, present):
    # GIVEN
    class MockInterpreter:
        pass

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
    activator = BashActivator(options)

    # WHEN
    activator.generate(creator)
    content = (creator.bin_dir / "activate").read_text(encoding="utf-8")

    # THEN
    # The teardown logic is always present in deactivate()
    assert "unset _OLD_VIRTUAL_TCL_LIBRARY" in content
    assert "unset _OLD_VIRTUAL_TK_LIBRARY" in content

    if present:
        assert 'if [ /path/to/tcl != "" ]; then' in content
        assert "TCL_LIBRARY=/path/to/tcl" in content
        assert "export TCL_LIBRARY" in content

        assert 'if [ /path/to/tk != "" ]; then' in content
        assert "TK_LIBRARY=/path/to/tk" in content
        assert "export TK_LIBRARY" in content
    else:
        # When not present, the if condition is false, so the block is not executed
        assert "if [ '' != \"\" ]; then" in content, content
        assert "TCL_LIBRARY=''" in content
        # The export is inside the if, so this is fine
        assert "export TCL_LIBRARY" in content


@pytest.mark.skipif(IS_WIN, reason="Github Actions ships with WSL bash")
@pytest.mark.parametrize("hashing_enabled", [True, False])
def test_bash(raise_on_non_source_class, hashing_enabled, activation_tester):
    class Bash(raise_on_non_source_class):
        def __init__(self, session) -> None:
            super().__init__(
                BashActivator,
                session,
                "bash",
                "activate",
                "sh",
                "You must source this script: $ source ",
            )
            self.deactivate += " || exit 1"
            self._invoke_script.append("-h" if hashing_enabled else "+h")

        def activate_call(self, script):
            return super().activate_call(script) + " || exit 1"

        def print_prompt(self):
            return self.print_os_env_var("PS1")

    activation_tester(Bash)
