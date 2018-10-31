import subprocess
import sys
from os.path import join, normcase

import pytest

import virtualenv
from tests.lib import need_executable

POWER_SHELL = "powershell.exe" if virtualenv.is_win else "pwsh"


def need_powershell(fn):
    return pytest.mark.powershell(
        need_executable("powershell", (POWER_SHELL, "-Command", "$PSVersionTable.PsVersion"))(fn)
    )


def print_python_exe_path():
    return "{} -c 'import sys; print(sys.executable)'".format(virtualenv.expected_exe)


@need_powershell
def test_activate_with_powershell(tmpdir, monkeypatch):
    monkeypatch.chdir(tmpdir)
    home_dir, _, __, bin_dir = virtualenv.path_locations(str(tmpdir.join("env")))
    virtualenv.create_environment(home_dir, no_pip=True, no_setuptools=True, no_wheel=True)
    monkeypatch.chdir(home_dir)
    activate_script = join(bin_dir, "activate.ps1")
    cmd = [POWER_SHELL, "-Command", "{0}; {1}; {0}; deactivate; {0}".format(print_python_exe_path(), activate_script)]
    output = subprocess.check_output(cmd, universal_newlines=True, stderr=subprocess.STDOUT)
    content = output.split()
    assert len(content) == 3, output
    before_activate, after_activate, after_deactivate = content
    exe = "{}.exe".format(virtualenv.expected_exe) if virtualenv.is_win else virtualenv.expected_exe
    assert normcase(long_path(after_activate)) == normcase(long_path(join(bin_dir, exe)))
    assert before_activate == after_deactivate


def long_path(short_path_name):
    # python 2 may return Windows short paths, normalize
    if virtualenv.is_win and sys.version_info < (3,):
        from ctypes import create_unicode_buffer, windll

        buffer_cont = create_unicode_buffer(256)
        get_long_path_name = windll.kernel32.GetLongPathNameW
        get_long_path_name(unicode(short_path_name), buffer_cont, 256)  # noqa: F821
        return buffer_cont.value
    return short_path_name
