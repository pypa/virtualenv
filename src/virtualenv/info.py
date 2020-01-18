from __future__ import absolute_import, unicode_literals

import logging
import os
import platform
import sys
import tempfile

from appdirs import user_config_dir, user_data_dir

IMPLEMENTATION = platform.python_implementation()
IS_PYPY = IMPLEMENTATION == "PyPy"
IS_CPYTHON = IMPLEMENTATION == "CPython"
PY3 = sys.version_info[0] == 3
IS_WIN = sys.platform == "win32"
ROOT = os.path.realpath(os.path.join(os.path.abspath(__file__), os.path.pardir, os.path.pardir))
IS_ZIPAPP = os.path.isfile(ROOT)
_FS_CASE_SENSITIVE = _CFG_DIR = _DATA_DIR = None


def get_default_data_dir():
    from virtualenv.util.path import Path

    global _DATA_DIR
    if _DATA_DIR is None:
        key = str("_VIRTUALENV_OVERRIDE_APP_DATA")
        folder = os.environ[key] if key in os.environ else user_data_dir(appname="virtualenv", appauthor="pypa")
        _DATA_DIR = Path(folder)
    return _DATA_DIR


def get_default_config_dir():
    from virtualenv.util.path import Path

    global _CFG_DIR
    if _CFG_DIR is None:
        _CFG_DIR = Path(user_config_dir(appname="virtualenv", appauthor="pypa"))
    return _CFG_DIR


def is_fs_case_sensitive():
    global _FS_CASE_SENSITIVE

    if _FS_CASE_SENSITIVE is None:
        with tempfile.NamedTemporaryFile(prefix="TmP") as tmp_file:
            _FS_CASE_SENSITIVE = not os.path.exists(tmp_file.name.lower())
            logging.debug(
                "filesystem under %r is %scase-sensitive", tmp_file.name, "" if _FS_CASE_SENSITIVE else "not "
            )
    return _FS_CASE_SENSITIVE


__all__ = (
    "IS_PYPY",
    "IS_CPYTHON",
    "PY3",
    "IS_WIN",
    "get_default_data_dir",
    "get_default_config_dir",
    "is_fs_case_sensitive",
    "ROOT",
    "IS_ZIPAPP",
)
