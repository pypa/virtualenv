import virtualenv
from mock import patch, Mock
import os.path
import sys

def test_version():
    """Should have a version string"""
    assert virtualenv.virtualenv_version == "1.6", "Should have version"

@patch('os.path.exists')
@patch('os.path.abspath')
def test_resolve_interpreter_with_absolute_path(mock_abspath, mock_exists):
    """Should return absolute path if given and exists"""
    mock_abspath.return_value = True
    mock_exists.return_value = True
    virtualenv.is_executable = Mock(return_value=True)

    mock_abspath.start()
    mock_exists.start()

    exe = virtualenv.resolve_interpreter("/usr/bin/python42")

    assert exe == "/usr/bin/python42", "Absolute path should return as is"
    mock_abspath.assert_called_with("/usr/bin/python42")
    mock_exists.assert_called_with("/usr/bin/python42")
    virtualenv.is_executable.assert_called_with("/usr/bin/python42")

    mock_abspath.stop()
    mock_exists.stop()

@patch('os.path.exists')
@patch('os.path.abspath')
def test_resolve_intepreter_with_nonexistant_interpreter(mock_abspath, mock_exists):
    """Should exit when with absolute path if not exists"""
    mock_abspath.return_value = True
    mock_exists.return_value = False
    
    mock_abspath.start()
    mock_exists.start()

    try:
        exe = virtualenv.resolve_interpreter("/usr/bin/python42")
        assert False, "Should raise exception"
    except SystemExit:
        pass
        
    mock_abspath.assert_called_with("/usr/bin/python42")
    mock_exists.assert_called_with("/usr/bin/python42")

    mock_abspath.stop()
    mock_exists.stop()

@patch('os.path.exists')
@patch('os.path.abspath')
def test_resolve_intepreter_with_invalid_interpreter(mock_abspath, mock_exists):
    """Should exit when with absolute path if not exists"""
    mock_abspath.return_value = True
    mock_exists.return_value = True
    virtualenv.is_executable = Mock(return_value=False)
    
    mock_abspath.start()
    mock_exists.start()

    try:
        exe = virtualenv.resolve_interpreter("/usr/bin/python42")
        assert False, "Should raise exception"
    except SystemExit:
        pass
        
    mock_abspath.assert_called_with("/usr/bin/python42")
    mock_exists.assert_called_with("/usr/bin/python42")
    virtualenv.is_executable.assert_called_with("/usr/bin/python42")

    mock_abspath.stop()
    mock_exists.stop()
