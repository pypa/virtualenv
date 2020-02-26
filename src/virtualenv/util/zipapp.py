from __future__ import absolute_import, unicode_literals

import logging
import os
import zipfile
from contextlib import contextmanager
from tempfile import TemporaryFile

from virtualenv.info import IS_WIN, IS_ZIPAPP, ROOT
from virtualenv.util.path import Path
from virtualenv.util.six import ensure_text
from virtualenv.version import __version__


def read(full_path):
    sub_file = _get_path_within_zip(full_path)
    with zipfile.ZipFile(ROOT, "r") as zip_file:
        with zip_file.open(sub_file) as file_handler:
            return file_handler.read().decode("utf-8")


def extract(full_path, dest):
    logging.debug("extract %s to %s", full_path, dest)
    sub_file = _get_path_within_zip(full_path)
    with zipfile.ZipFile(ROOT, "r") as zip_file:
        info = zip_file.getinfo(sub_file)
        info.filename = dest.name
        zip_file.extract(info, ensure_text(str(dest.parent)))


def _get_path_within_zip(full_path):
    full_path = os.path.abspath(str(full_path))
    sub_file = full_path[len(ROOT) + 1 :]
    if IS_WIN:
        # paths are always UNIX separators, even on Windows, though __file__ still follows platform default
        sub_file = sub_file.replace(os.sep, "/")
    return sub_file


@contextmanager
def ensure_file_on_disk(path, app_data):
    if IS_ZIPAPP:
        if app_data is None:
            with TemporaryFile() as temp_file:
                dest = Path(temp_file.name)
                extract(path, dest)
                yield Path(dest)
        else:
            base = app_data / "zipapp" / "extract" / __version__
            with base.lock_for_key(path.name):
                dest = base.path / path.name
                if not dest.exists():
                    extract(path, dest)
                yield dest
    else:
        yield path
