from __future__ import absolute_import, unicode_literals

import sys

if sys.version_info > (3,):
    from shutil import which
else:
    from distutils.spawn import find_executable as which


from virtualenv.activation import NushellActivator
from virtualenv.info import IS_WIN


def test_nushell(activation_tester_class, activation_tester):
    class Nushell(activation_tester_class):
        def __init__(self, session):
            cmd = which("nu")
            if cmd is None and IS_WIN:
                cmd = "c:\\program files\\nu\\bin\\nu.exe"

            super(Nushell, self).__init__(NushellActivator, session, cmd, "activate.nu", "nu")

            self.unix_line_ending = not IS_WIN

        def print_prompt(self):
            return r"echo $virtual_prompt; printf '\n'"

    activation_tester(Nushell)
