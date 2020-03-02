from __future__ import absolute_import, unicode_literals

import os
import pipes
import sys

from virtualenv.activation import BatchActivator


def test_batch(activation_tester_class, activation_tester, tmp_path, activation_python):
    version_script = tmp_path / "version.bat"
    version_script.write_text("ver")

    class Batch(activation_tester_class):
        def __init__(self, session):
            super(Batch, self).__init__(BatchActivator, session, None, "activate.bat", "bat")
            self._version_cmd = [str(version_script)]
            self._invoke_script = []
            self.deactivate = "call deactivate"
            self.activate_cmd = "call"
            self.pydoc_call = "call {}".format(self.pydoc_call)

        def _get_test_lines(self, activate_script):
            # for BATCH utf-8 support need change the character code page to 650001
            return [
                "@echo off",
                "",
                "chcp 65001 1>NUL",
                self.print_python_exe(),
                self.print_os_env_var("PROMPT"),
                self.print_os_env_var("VIRTUAL_ENV"),
                self.activate_call(activate_script),
                self.print_python_exe(),
                self.print_os_env_var("VIRTUAL_ENV"),
                # \\ loads documentation from the virtualenv site packages
                self.pydoc_call,
                self.print_os_env_var("PROMPT"),
                self.deactivate,
                self.print_python_exe(),
                self.print_os_env_var("VIRTUAL_ENV"),
                self.print_os_env_var("PROMPT"),
                "",  # just finish with an empty new line
            ]

        def assert_output(self, out, raw, tmp_path):
            # pre-activation
            assert out[0], raw
            assert out[2] == "None", raw
            # post-activation
            expected = self._creator.exe.parent / os.path.basename(sys.executable)
            assert self.norm_path(out[3]) == self.norm_path(expected), raw
            assert self.norm_path(out[4]) == self.norm_path(self._creator.dest).replace("\\\\", "\\"), raw
            assert out[5] == "wrote pydoc_test.html", raw
            content = tmp_path / "pydoc_test.html"
            assert os.path.basename(self._creator.dest) in out[6]
            assert content.exists(), raw
            # post deactivation, same as before
            assert out[-3] == out[0], raw
            assert out[-2] == "None", raw
            assert out[1] == out[-1], raw

        def quote(self, s):
            """double quotes needs to be single, and single need to be double"""
            return "".join(("'" if c == '"' else ('"' if c == "'" else c)) for c in pipes.quote(s))

    activation_tester(Batch)
