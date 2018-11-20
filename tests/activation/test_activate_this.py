import os


def get_base_dir():
    return os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir))


def get_activate_this_path():
    return os.path.abspath(os.path.join(get_base_dir(), 'virtualenv_embedded', 'activate_this.py'))


def activate():
    activate_this = get_activate_this_path()
    exec(compile(open(activate_this).read(), activate_this, 'exec'), dict(__file__=activate_this))


def test_activate_this():
    base_dir = get_base_dir()
    old_path = os.environ['PATH']

    activate()

    assert os.environ['PATH'] == os.path.dirname(get_activate_this_path()) + os.pathsep + old_path
    assert os.environ['VIRTUAL_ENV'] == base_dir
