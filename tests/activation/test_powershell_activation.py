import os
import subprocess

import pytest

import virtualenv
from tests.lib import need_executable

POWER_SHELL = "powershell.exe" if virtualenv.is_win else "pwsh"


def need_powershell(fn):
    return pytest.mark.powershell(
        need_executable("powershell", (POWER_SHELL, "-Command", "$PSVersionTable.PsVersion"))(fn)
    )


def print_python_exe_path():
    return "python -c 'import sys; print(sys.executable)'"


@need_powershell
def test_activate_with_powershell(tmpdir, monkeypatch):
    monkeypatch.chdir(tmpdir)
    home_dir, _, __, bin_dir = virtualenv.path_locations(str(tmpdir.join("env")))
    virtualenv.create_environment(home_dir, no_pip=True, no_setuptools=True, no_wheel=True)
    monkeypatch.chdir(home_dir)
    activate_script = os.path.join(bin_dir, "activate.ps1")
    cmd = [POWER_SHELL, "-Command", "{0}; {1}; {0}; deactivate; {0}".format(print_python_exe_path(), activate_script)]
    output = subprocess.check_output(cmd, universal_newlines=True, stderr=subprocess.STDOUT)
    content = output.split()
    assert len(content) == 3, output
    before_activate, after_activate, after_deactivate = content
    assert after_activate == os.path.join(bin_dir, "python.exe" if virtualenv.is_win else "python")
    assert before_activate == after_deactivate
