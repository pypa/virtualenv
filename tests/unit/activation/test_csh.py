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

        def _get_test_lines(self, activate_script):
            lines = super()._get_test_lines(activate_script)
            lines.insert(3, self.print_os_env_var("PKG_CONFIG_PATH"))
            i = next(i for i, line in enumerate(lines) if "pydoc" in line)
            lines.insert(i, self.print_os_env_var("PKG_CONFIG_PATH"))
            lines.insert(-1, self.print_os_env_var("PKG_CONFIG_PATH"))
            return lines

        def assert_output(self, out, raw, tmp_path):
            assert out[3] == "None"

            pkg_config_path = self.norm_path(self._creator.dest / "lib" / "pkgconfig")
            assert self.norm_path(out[9]) == pkg_config_path

            assert out[-2] == "None"
            super().assert_output(out[:3] + out[4:9] + out[10:-2] + [out[-1]], raw, tmp_path)

    activation_tester(Csh)
