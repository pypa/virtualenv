from __future__ import absolute_import, unicode_literals

import subprocess
import sys

import six

if six.PY2 and sys.platform == "win32":
    from . import win_subprocess

    Popen = win_subprocess.Popen
else:
    Popen = subprocess.Popen

__all__ = ("subprocess", "Popen")
