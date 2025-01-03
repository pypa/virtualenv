from __future__ import annotations

import sys
from shutil import which
from subprocess import check_output

import pytest
from packaging.version import Version

from virtualenv.activation import CShellActivator


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
