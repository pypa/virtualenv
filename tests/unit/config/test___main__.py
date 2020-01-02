from __future__ import absolute_import, unicode_literals

import sys

from virtualenv.util.subprocess import Popen, subprocess


def test_main():
    process = Popen([sys.executable, "-m", "virtualenv", "--help"], universal_newlines=True, stdout=subprocess.PIPE)
    out, _ = process.communicate()
    assert not process.returncode
    assert out
