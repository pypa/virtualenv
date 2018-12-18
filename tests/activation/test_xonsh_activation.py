from os.path import join

import virtualenv
from tests.lib import need_executable

XONSH_COMMAND = "xonsh.exe" if virtualenv.is_win else "xonsh"


def need_xonsh(fn):
    return need_executable("xonsh", (XONSH_COMMAND, "--version"))(fn)


@need_xonsh
def test_activate_with_xonsh(activation_tester, print_python_exe_path):
    activate_script = join(activation_tester.bin_dir, "activate.xsh")
    activation_tester(
        XONSH_COMMAND, "-c", "{0}; source r'{1}'; {0}; deactivate; {0}".format(print_python_exe_path, activate_script)
    )
