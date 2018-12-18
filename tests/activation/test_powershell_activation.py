from os.path import join

import virtualenv
from tests.lib import need_executable

POWER_SHELL = "powershell.exe" if virtualenv.is_win else "pwsh"


def need_powershell(fn):
    return need_executable("powershell", (POWER_SHELL, "-Command", "$PSVersionTable.PsVersion"))(fn)


@need_powershell
def test_activate_with_powershell(activation_tester, print_python_exe_path):
    activate_script = join(activation_tester.bin_dir, "activate.ps1")
    activation_tester(
        POWER_SHELL, "-Command", "{0}; {1}; {0}; deactivate; {0}".format(print_python_exe_path, activate_script)
    )
