from shutil import which

from virtualenv.activation import NushellActivator
from virtualenv.info import IS_WIN


def test_nushell(activation_tester_class, activation_tester):
    class Nushell(activation_tester_class):
        def __init__(self, session):
            cmd = which("nu")
            if cmd is None and IS_WIN:
                cmd = "c:\\program files\\nu\\bin\\nu.exe"

            super().__init__(NushellActivator, session, cmd, "activate.nu", "nu")

            self.unix_line_ending = not IS_WIN

        def print_prompt(self):
            return r"$env.VIRTUAL_PROMPT"

    activation_tester(Nushell)
