from __future__ import absolute_import, unicode_literals

import logging
import os
import zipfile

import six

from virtualenv.info import IS_WIN, ROOT, get_default_data_dir
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
        zip_file.extract(info, six.ensure_text(str(dest.parent)))


def _get_path_within_zip(full_path):
    sub_file = str(full_path)[len(ROOT) + 1 :]
    if IS_WIN:
        # paths are always UNIX separators, even on Windows, though __file__ still follows platform default
        sub_file = sub_file.replace(os.sep, "/")
    return sub_file


def extract_to_app_data(full_path):
    base = get_default_data_dir() / "zipapp" / "extract" / __version__
    base.mkdir(parents=True, exist_ok=True)
    dest = base / full_path.name
    if not dest.exists():
        extract(full_path, dest)
    return dest
