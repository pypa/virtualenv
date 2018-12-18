import os
import subprocess
import sys
from os.path import join, normcase

import pytest

import virtualenv


@pytest.fixture(scope="session")
def activation_env(tmp_path_factory):
    path = tmp_path_factory.mktemp("activation-test-env")
    prev_cwd = os.getcwd()
    try:
        os.chdir(str(path))
        home_dir, _, __, bin_dir = virtualenv.path_locations(str(path / "env"))
        virtualenv.create_environment(home_dir, no_pip=True, no_setuptools=True, no_wheel=True)
        return home_dir, bin_dir
    finally:
        os.chdir(prev_cwd)


@pytest.fixture(scope="session")
def print_python_exe_path():
    return "{} -c 'import sys; print(sys.executable)'".format(virtualenv.expected_exe)


@pytest.fixture(scope="function")
def activation_tester(activation_env, monkeypatch):
    home_dir, bin_dir = activation_env

    def call(*cmd):
        monkeypatch.chdir(home_dir)
        output = subprocess.check_output(cmd, universal_newlines=True, stderr=subprocess.STDOUT)
        content = output.split()
        assert len(content) >= 3, output
        before_activate, after_activate, after_deactivate = content
        exe = "{}.exe".format(virtualenv.expected_exe) if virtualenv.is_win else virtualenv.expected_exe
        assert normcase(long_path(after_activate)) == normcase(long_path(join(bin_dir, exe)))
        assert before_activate == after_deactivate
        return content[3:]

    call.bin_dir = bin_dir

    return call


def long_path(short_path_name):
    # python 2 may return Windows short paths, normalize
    if virtualenv.is_win and sys.version_info < (3,):
        from ctypes import create_unicode_buffer, windll

        buffer_cont = create_unicode_buffer(256)
        get_long_path_name = windll.kernel32.GetLongPathNameW
        # noinspection PyUnresolvedReferences
        get_long_path_name(unicode(short_path_name), buffer_cont, 256)  # noqa: F821
        return buffer_cont.value
    return short_path_name
