from __future__ import absolute_import, unicode_literals

import sys

from virtualenv.activation import NushellActivator


def test_nushell(activation_tester_class, activation_tester):
    class Nushell(activation_tester_class):
        def __init__(self, session):
            cmd = "c:\\program files\\nu\\bin\\nu.exe" if sys.platform == "win32" else "nu"
            super(Nushell, self).__init__(NushellActivator, session, cmd, "activate.nu", "nu")

    activation_tester(Nushell)
