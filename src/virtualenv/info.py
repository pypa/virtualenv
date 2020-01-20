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

_CAN_SYMLINK = _FS_CASE_SENSITIVE = _CFG_DIR = _DATA_DIR = None


def default_data_dir():
    from virtualenv.util.path import Path

    global _DATA_DIR
    if _DATA_DIR is None:
        key = str("_VIRTUALENV_OVERRIDE_APP_DATA")
        folder = os.environ[key] if key in os.environ else user_data_dir(appname="virtualenv", appauthor="pypa")
        _DATA_DIR = Path(folder)
    return _DATA_DIR


def default_config_dir():
    from virtualenv.util.path import Path

    global _CFG_DIR
    if _CFG_DIR is None:
        _CFG_DIR = Path(user_config_dir(appname="virtualenv", appauthor="pypa"))
    return _CFG_DIR


def fs_is_case_sensitive():
    global _FS_CASE_SENSITIVE

    if _FS_CASE_SENSITIVE is None:
        with tempfile.NamedTemporaryFile(prefix="TmP") as tmp_file:
            _FS_CASE_SENSITIVE = not os.path.exists(tmp_file.name.lower())
            logging.debug("filesystem is %scase-sensitive", "" if _FS_CASE_SENSITIVE else "not ")
    return _FS_CASE_SENSITIVE


def fs_supports_symlink():
    global _CAN_SYMLINK

    if _CAN_SYMLINK is None:
        can = False
        if hasattr(os, "symlink"):
            if IS_WIN:
                with tempfile.NamedTemporaryFile(prefix="TmP") as tmp_file:
                    temp_dir = os.path.dirname(tmp_file.name)
                    dest = os.path.join(temp_dir, "{}-{}".format(tmp_file.name, "b"))
                    try:
                        os.symlink(tmp_file.name, dest)
                        can = True
                    except OSError:
                        pass
                logging.debug("symlink on filesystem does%s work", "" if can else " not")
            else:
                can = True
        _CAN_SYMLINK = can
    return _CAN_SYMLINK


__all__ = (
    "IS_PYPY",
    "IS_CPYTHON",
    "PY3",
    "IS_WIN",
    "default_data_dir",
    "default_config_dir",
    "fs_is_case_sensitive",
    "fs_supports_symlink",
    "ROOT",
    "IS_ZIPAPP",
)
