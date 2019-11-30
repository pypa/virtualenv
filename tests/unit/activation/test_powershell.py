from __future__ import absolute_import, unicode_literals

import pipes
import sys

from virtualenv.activation import PowerShellActivator


def test_powershell(activation_tester_class, activation_tester):
    class PowerShell(activation_tester_class):
        def __init__(self, session):
            cmd = "powershell.exe" if sys.platform == "win32" else "pwsh"
            super(PowerShell, self).__init__(PowerShellActivator, session, cmd, "activate.ps1", "ps1")
            self._version_cmd = [self.cmd, "-c", "$PSVersionTable"]
            self.activate_cmd = "."

        def quote(self, s):
            """powershell double double quote needed for quotes within single quotes"""
            return pipes.quote(s).replace('"', '""')

        def invoke_script(self):
            return [self.cmd, "-File"]

    activation_tester(PowerShell)
