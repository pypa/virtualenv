import os
import tempfile

from appdirs import user_config_dir, user_data_dir

from virtualenv.util.lock import ReentrantFileLock

_DATA_DIR = None
_CFG_DIR = None


def default_data_dir():

    global _DATA_DIR
    if _DATA_DIR is None:
        folder = _get_default_data_folder()
        _DATA_DIR = ReentrantFileLock(folder)
    return _DATA_DIR


def _get_default_data_folder():
    key = str("VIRTUALENV_OVERRIDE_APP_DATA")
    if key in os.environ:
        folder = os.environ[key]
    else:
        folder = user_data_dir(appname="virtualenv", appauthor="pypa")

    if not _writable(folder):
        folder = os.path.join(tempfile.gettempdir(), "virtualenv")
    return folder


def _writable(folder) -> bool:
    head = os.path.normpath(folder)

    while not (os.path.exists(head) and os.access(head, os.W_OK)):
        head, tail = os.path.split(head)
        if not tail:
            return False

    return True


def default_config_dir():
    from virtualenv.util.path import Path

    global _CFG_DIR
    if _CFG_DIR is None:
        _CFG_DIR = Path(user_config_dir(appname="virtualenv", appauthor="pypa"))
    return _CFG_DIR


__all__ = (
    "default_data_dir",
    "default_config_dir",
)
