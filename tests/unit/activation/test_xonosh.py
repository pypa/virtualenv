from __future__ import absolute_import, unicode_literals

import sys


def test_xonosh(activation_tester_class, activation_tester):
    class Xonosh(activation_tester_class):
        def __init__(self, session):
            super(Xonosh, self).__init__(session, "xonsh", "activate.xsh", "xsh")
            self._invoke_script = [sys.executable, "-m", "xonsh"]
            self.__version_cmd = [sys.executable, "-m", "xonsh", "--version"]

        def env(self, tmp_path):
            env = super(Xonosh, self).env(tmp_path)
            env.update({"XONSH_DEBUG": "1", "XONSH_SHOW_TRACEBACK": "True"})
            return env

        def activate_call(self, script):
            return "{} {}".format(self.activate_cmd, repr(str(script))).strip()

    activation_tester(Xonosh)
