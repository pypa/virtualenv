from __future__ import annotations

import sys
from argparse import Namespace
from shutil import which
from subprocess import check_output

import pytest
from packaging.version import Version

from virtualenv.activation import CShellActivator


@pytest.mark.parametrize(
    ("tcl_lib", "tk_lib", "present"),
    [
        ("/path/to/tcl", "/path/to/tk", True),
        (None, None, False),
    ],
)
def test_cshell_tkinter_generation(tmp_path, tcl_lib, tk_lib, present):
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
    activator = CShellActivator(options)

    # WHEN
    activator.generate(creator)
    content = (creator.bin_dir / "activate.csh").read_text(encoding="utf-8")

    if present:
        assert "test $?_OLD_VIRTUAL_TCL_LIBRARY != 0" in content
        assert "test $?_OLD_VIRTUAL_TK_LIBRARY != 0" in content
        assert "setenv TCL_LIBRARY /path/to/tcl" in content
        assert "setenv TK_LIBRARY /path/to/tk" in content
    else:
        assert "setenv TCL_LIBRARY ''" in content


def test_csh(activation_tester_class, activation_tester):
    exe = f"tcsh{'.exe' if sys.platform == 'win32' else ''}"
    if which(exe):
        version_text = check_output([exe, "--version"], text=True, encoding="utf-8")
        version = Version(version_text.split(" ")[1])
        if version >= Version("6.24.14"):
            pytest.skip("https://github.com/tcsh-org/tcsh/issues/117")

    class Csh(activation_tester_class):
        def __init__(self, session) -> None:
            super().__init__(CShellActivator, session, "csh", "activate.csh", "csh")

        def print_prompt(self):
            # Original csh doesn't print the last newline,
            # breaking the test; hence the trailing echo.
            return "echo 'source \"$VIRTUAL_ENV/bin/activate.csh\"; echo $prompt' | csh -i ; echo"

    activation_tester(Csh)
