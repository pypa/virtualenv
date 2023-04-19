from __future__ import annotations

import pytest

from virtualenv.activation import BashActivator
from virtualenv.info import IS_WIN


@pytest.mark.skipif(IS_WIN, reason="Github Actions ships with WSL bash")
def test_bash(raise_on_non_source_class, activation_tester):
    class Bash(raise_on_non_source_class):
        def __init__(self, session):
            super().__init__(
                BashActivator,
                session,
                "bash",
                "activate",
                "sh",
                "You must source this script: $ source ",
            )

        def print_prompt(self):
            return self.print_os_env_var("PS1")

    activation_tester(Bash)
