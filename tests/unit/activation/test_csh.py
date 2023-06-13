from __future__ import annotations

from virtualenv.activation import CShellActivator


def test_csh(activation_tester_class, activation_tester):
    class Csh(activation_tester_class):
        def __init__(self, session) -> None:
            super().__init__(CShellActivator, session, "csh", "activate.csh", "csh")

        def print_prompt(self):
            # Original csh doesn't print the last newline,
            # breaking the test; hence the trailing echo.
            return "echo 'source \"$VIRTUAL_ENV/bin/activate.csh\"; echo $prompt' | csh -i ; echo"

    activation_tester(Csh)
