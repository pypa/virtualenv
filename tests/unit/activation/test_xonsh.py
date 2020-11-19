from __future__ import absolute_import, unicode_literals

import sys

import pytest
from flaky import flaky

from virtualenv.activation import XonshActivator


@pytest.mark.slow
@pytest.mark.skipif(
    sys.platform == "win32" or sys.version_info[0:2] >= (3, 9),
    reason="xonsh on 3.9 or Windows is broken - https://github.com/xonsh/xonsh/issues/3689",
)
@flaky(max_runs=2, min_passes=1)
def test_xonsh(activation_tester_class, activation_tester):
    class Xonsh(activation_tester_class):
        def __init__(self, session):
            super(Xonsh, self).__init__(
                XonshActivator,
                session,
                "xonsh.exe" if sys.platform == "win32" else "xonsh",
                "activate.xsh",
                "xsh",
            )
            self._invoke_script = [sys.executable, "-m", "xonsh"]
            self._version_cmd = [sys.executable, "-m", "xonsh", "--version"]

        def env(self, tmp_path):
            env = super(Xonsh, self).env(tmp_path)
            env.update({"XONSH_DEBUG": "1", "XONSH_SHOW_TRACEBACK": "True"})
            return env

        def activate_call(self, script):
            return "{} {}".format(self.activate_cmd, repr(str(script))).strip()

    activation_tester(Xonsh)
