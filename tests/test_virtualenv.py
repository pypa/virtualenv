import virtualenv
import optparse
import os
import shutil
import sys
import tempfile
import pytest
import platform  # noqa

from mock import patch, Mock


def test_version():
    """Should have a version string"""
    assert virtualenv.virtualenv_version, "Should have version"


@patch('distutils.spawn.find_executable')
@patch('virtualenv.is_executable', return_value=True)
@patch('virtualenv.get_installed_pythons')
@patch('os.path.exists', return_value=True)
@patch('os.path.abspath')
def test_resolve_interpreter_with_installed_python(mock_abspath, mock_exists,
        mock_get_installed_pythons, mock_is_executable, mock_find_executable):
    test_tag = 'foo'
    test_path = '/path/to/foo/python.exe'
    test_abs_path = 'some-abs-path'
    test_found_path = 'some-found-path'
    mock_get_installed_pythons.return_value = {
        test_tag: test_path,
        test_tag + '2': test_path + '2'}
    mock_abspath.return_value = test_abs_path
    mock_find_executable.return_value = test_found_path

    exe = virtualenv.resolve_interpreter('foo')

    assert exe == test_found_path, \
        "installed python should be accessible by key"

    mock_get_installed_pythons.assert_called_once_with()
    mock_abspath.assert_called_once_with(test_path)
    mock_find_executable.assert_called_once_with(test_path)
    mock_exists.assert_called_once_with(test_found_path)
    mock_is_executable.assert_called_once_with(test_found_path)


@patch('virtualenv.is_executable', return_value=True)
@patch('virtualenv.get_installed_pythons', return_value={'foo': 'bar'})
@patch('os.path.exists', return_value=True)
def test_resolve_interpreter_with_absolute_path(
        mock_exists, mock_get_installed_pythons, mock_is_executable):
    """Should return absolute path if given and exists"""
    test_abs_path = os.path.abspath("/usr/bin/python53")

    exe = virtualenv.resolve_interpreter(test_abs_path)

    assert exe == test_abs_path, "Absolute path should return as is"

    mock_exists.assert_called_with(test_abs_path)
    mock_is_executable.assert_called_with(test_abs_path)


@patch('virtualenv.get_installed_pythons', return_value={'foo': 'bar'})
@patch('os.path.exists', return_value=False)
def test_resolve_interpreter_with_nonexistent_interpreter(
        mock_exists, mock_get_installed_pythons):
    """Should SystemExit with an nonexistent python interpreter path"""
    with pytest.raises(SystemExit):
        virtualenv.resolve_interpreter("/usr/bin/python53")

    mock_exists.assert_called_with("/usr/bin/python53")


@patch('virtualenv.is_executable', return_value=False)
@patch('os.path.exists', return_value=True)
def test_resolve_interpreter_with_invalid_interpreter(mock_exists,
                                                      mock_is_executable):
    """Should exit when with absolute path if not exists"""
    invalid = os.path.abspath("/usr/bin/pyt_hon53")

    with pytest.raises(SystemExit):
        virtualenv.resolve_interpreter(invalid)

    mock_exists.assert_called_with(invalid)
    mock_is_executable.assert_called_with(invalid)


def test_activate_after_future_statements():
    """Should insert activation line after last future statement"""
    script = [
        '#!/usr/bin/env python',
        'from __future__ import with_statement',
        'from __future__ import print_function',
        'print("Hello, world!")'
    ]
    assert virtualenv.relative_script(script) == [
        '#!/usr/bin/env python',
        'from __future__ import with_statement',
        'from __future__ import print_function',
        '',
        "import os; activate_this=os.path.join(os.path.dirname(os.path.realpath(__file__)), 'activate_this.py'); exec(compile(open(activate_this).read(), activate_this, 'exec'), dict(__file__=activate_this)); del os, activate_this",
        '',
        'print("Hello, world!")'
    ]


def test_cop_update_defaults_with_store_false():
    """store_false options need reverted logic"""
    class MyConfigOptionParser(virtualenv.ConfigOptionParser):
        def __init__(self, *args, **kwargs):
            self.config = virtualenv.ConfigParser.RawConfigParser()
            self.files = []
            optparse.OptionParser.__init__(self, *args, **kwargs)

        def get_environ_vars(self, prefix='VIRTUALENV_'):
            yield ("no_site_packages", "1")

    cop = MyConfigOptionParser()
    cop.add_option(
        '--no-site-packages',
        dest='system_site_packages',
        action='store_false',
        help="Don't give access to the global site-packages dir to the "
             "virtual environment (default)")

    defaults = {}
    cop.update_defaults(defaults)
    assert defaults == {'system_site_packages': 0}


def test_install_python_bin():
    """Should create the right python executables and links"""
    tmp_virtualenv = tempfile.mkdtemp()
    try:
        home_dir, lib_dir, inc_dir, bin_dir = \
                                virtualenv.path_locations(tmp_virtualenv)
        virtualenv.install_python(home_dir, lib_dir, inc_dir, bin_dir, False,
                                  False)

        if virtualenv.is_win:
            required_executables = ['python.exe', 'pythonw.exe']
        else:
            py_exe_no_version = 'python'
            py_exe_version_major = 'python%s' % sys.version_info[0]
            py_exe_version_major_minor = 'python%s.%s' % (
                sys.version_info[0], sys.version_info[1])
            required_executables = [py_exe_no_version, py_exe_version_major,
                                    py_exe_version_major_minor]

        for pth in required_executables:
            assert os.path.exists(os.path.join(bin_dir, pth)), \
                   ("%s should exist in bin_dir" % pth)
    finally:
        shutil.rmtree(tmp_virtualenv)


@pytest.mark.skipif("platform.python_implementation() == 'PyPy'")
def test_always_copy_option():
    """Should be no symlinks in directory tree"""
    tmp_virtualenv = tempfile.mkdtemp()
    ve_path = os.path.join(tmp_virtualenv, 'venv')
    try:
        virtualenv.create_environment(ve_path, symlink=False)

        for root, dirs, files in os.walk(tmp_virtualenv):
            for f in files + dirs:
                full_name = os.path.join(root, f)
                assert not os.path.islink(full_name), "%s should not be a" \
                    " symlink (to %s)" % (full_name, os.readlink(full_name))
    finally:
        shutil.rmtree(tmp_virtualenv)
