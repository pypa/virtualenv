import virtualenv
import optparse
from mock import patch, Mock


def test_version():
    """Should have a version string"""
    assert virtualenv.virtualenv_version, "Should have version"


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
