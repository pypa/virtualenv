import sys
from os.path import join

import pytest

import virtualenv
from tests.lib import need_executable

FISH_COMMAND = "fish.exe" if virtualenv.is_win else "fish"


def need_fish(fn):
    return need_executable("fish", (FISH_COMMAND, "--version"))(fn)


@need_fish
@pytest.mark.skipif(sys.platform == "win32", reason="no sane way to provision fish on Windows yet")
def test_activation_with_fish(activation_tester, print_python_exe_path):
    activate_script = join(activation_tester.bin_dir, "activate.fish")
    activation_tester(
        FISH_COMMAND, "-c", "{0}; source {1}; {0}; deactivate; {0}".format(print_python_exe_path, activate_script)
    )
