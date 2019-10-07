from __future__ import absolute_import, unicode_literals

import sys

from appdirs import user_config_dir, user_data_dir
from pathlib2 import Path

IS_PYPY = hasattr(sys, "pypy_version_info")
PY3 = sys.version_info[0] == 3
IS_WIN = sys.platform == "win32"


_DATA_DIR = Path(user_data_dir(appname="virtualenv", appauthor="pypa"))
_CONFIG_DIR = Path(user_config_dir(appname="virtualenv", appauthor="pypa"))


def get_default_data_dir():
    return _DATA_DIR


def get_default_config_dir():
    return _CONFIG_DIR


__all__ = ("IS_PYPY", "PY3", "IS_WIN", "get_default_data_dir", "get_default_config_dir")
