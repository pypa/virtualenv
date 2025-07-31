from __future__ import annotations

import pytest

from virtualenv.activation import BashActivator
from virtualenv.info import IS_WIN


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

            assert out[-2] == "None"  # shell has no value
            super().assert_output(out[:3] + out[4:9] + out[10:-2] + [out[-1]], raw, tmp_path)

    activation_tester(Bash)
