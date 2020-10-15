from __future__ import absolute_import, unicode_literals

import subprocess
import sys

import pytest

from virtualenv.info import IS_WIN, PY2
from virtualenv.util.subprocess import run_cmd


def test_run_fail(tmp_path):
    code, out, err = run_cmd([str(tmp_path)])
    assert err
    assert not out
    assert code


@pytest.mark.skipif(not (PY2 and IS_WIN), reason="subprocess patch only applied on Windows python2")
def test_windows_py2_cwd_works(tmp_path):
    cwd = str(tmp_path)
    result = subprocess.check_output(
        [sys.executable, "-c", "import os; print(os.getcwd())"],
        cwd=cwd,
        universal_newlines=True,
    )
    assert result == "{}\n".format(cwd)
