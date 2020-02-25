import os
import tempfile

from virtualenv import dirs
from virtualenv.dirs import _get_default_data_folder


def test_get_default_data_dir(monkeypatch):
    # given
    data_dirs = {
        "/.local/share": os.path.join(tempfile.gettempdir(), "virtualenv"),
        os.getenv('HOME'): os.path.join(os.getenv('HOME'), "virtualenv"),
        "/tmp/share/": os.path.join("/tmp/share", "virtualenv")
    }

    def user_data_dir(data_dir):
        def wrapper(appname=None, appauthor=None, version=None, roaming=False):
            return os.path.join(data_dir, appname)
        return wrapper

    for data_dir, expected in data_dirs.items():
        monkeypatch.setattr(dirs, "user_data_dir", user_data_dir(data_dir))

        # when
        actual = _get_default_data_folder()

        # then
        assert actual == expected
