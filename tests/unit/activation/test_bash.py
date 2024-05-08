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

    activation_tester(Bash)
