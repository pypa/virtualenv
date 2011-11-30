import virtualenv
from mock import patch, Mock


def test_version():
    """Should have a version string"""
    assert virtualenv.virtualenv_version == "1.7", "Should have version"


@patch('os.path.exists')
def test_resolve_interpreter_with_absolute_path(mock_exists):
    """Should return absolute path if given and exists"""
    mock_exists.return_value = True
    virtualenv.is_executable = Mock(return_value=True)

    exe = virtualenv.resolve_interpreter("/usr/bin/python42")

    assert exe == "/usr/bin/python42", "Absolute path should return as is"
    mock_exists.assert_called_with("/usr/bin/python42")
    virtualenv.is_executable.assert_called_with("/usr/bin/python42")


@patch('os.path.exists')
def test_resolve_intepreter_with_nonexistant_interpreter(mock_exists):
    """Should exit when with absolute path if not exists"""
    mock_exists.return_value = False

    try:
        virtualenv.resolve_interpreter("/usr/bin/python42")
        assert False, "Should raise exception"
    except SystemExit:
        pass

    mock_exists.assert_called_with("/usr/bin/python42")


@patch('os.path.exists')
def test_resolve_intepreter_with_invalid_interpreter(mock_exists):
    """Should exit when with absolute path if not exists"""
    mock_exists.return_value = True
    virtualenv.is_executable = Mock(return_value=False)

    try:
        virtualenv.resolve_interpreter("/usr/bin/python42")
        assert False, "Should raise exception"
    except SystemExit:
        pass

    mock_exists.assert_called_with("/usr/bin/python42")
    virtualenv.is_executable.assert_called_with("/usr/bin/python42")
