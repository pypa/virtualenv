import subprocess
import sys

import pytest

import virtualenv
from tests.lib import need_executable

POWER_SHELL = "powershell.exe" if sys.platform == "win32" else "pwsh"


def need_powershell(fn):
    return pytest.mark.powershell(
        need_executable("powershell", (POWER_SHELL, "-Command", "$PSVersionTable.PsVersion"))(fn)
    )


@need_powershell
def test_activate_with_powershell(tmpdir, monkeypatch):
    monkeypatch.chdir(tmpdir)
    ve_path = tmpdir.join("venv")
    virtualenv.create_environment(str(ve_path), no_pip=True, no_setuptools=True, no_wheel=True)
    monkeypatch.chdir(ve_path)
    activate_script = ve_path.join("bin", "activate.ps1")
    output = subprocess.check_output(
        [
            POWER_SHELL,
            "-c",
            "python -c 'import sys; print(sys.executable)'; "
            "{}; python -c 'import sys; print(sys.executable)'; ".format(activate_script),
            "deactivate; python -c 'import sys; print(sys.executable)'",
        ],
        universal_newlines=True,
    )

    before_activate, after_activate, after_deactivate = output.split()
    assert after_activate == str(ve_path.join("bin", "python"))
    assert before_activate == after_deactivate
