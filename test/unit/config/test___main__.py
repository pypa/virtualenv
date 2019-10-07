from __future__ import absolute_import, unicode_literals

import subprocess
import sys


def test_main():
    out = subprocess.check_output([sys.executable, "-m", "virtualenv", "--help"], universal_newlines=True)
    assert out
