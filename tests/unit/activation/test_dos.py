from __future__ import absolute_import, unicode_literals

import pipes


def test_dos(activation_tester_class, activation_tester, tmp_path, activation_python):
    version_script = tmp_path / "version.bat"
    version_script.write_text("ver")

    class DOS(activation_tester_class):
        def __init__(self, session):
            super(DOS, self).__init__(session, None, "activate.bat", "bat")
            self._version_cmd = [str(version_script)]
            self._invoke_script = []
            self.deactivate = "call {}".format(self.quote(str(activation_python.creator.bin_dir / "deactivate.bat")))
            self.activate_cmd = "call"

        def _get_test_lines(self, activate_script):
            return ["@echo off", ""] + super(DOS, self)._get_test_lines(activate_script)

        def quote(self, s):
            """double quotes needs to be single, and single need to be double"""
            return "".join(("'" if c == '"' else ('"' if c == "'" else c)) for c in pipes.quote(s))

    activation_tester(DOS)
