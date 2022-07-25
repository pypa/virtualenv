from contextlib import contextmanager

from .base import AppData, ContentStore


class AppDataDisabled(AppData):
    """No application cache available (most likely as we don't have write permissions)"""

    transient = True
    can_update = False

    def __init__(self):
        pass

    error = RuntimeError("no app data folder available, probably no write access to the folder")

    def close(self):
        """do nothing"""

    def reset(self):
        """do nothing"""

    def py_info(self, path):
        return ContentStoreNA()

    def embed_update_log(self, distribution, for_py_version):
        return ContentStoreNA()

    def extract(self, path, to_folder):
        raise self.error

    @contextmanager
    def locked(self, path):
        """do nothing"""
        yield

    @property
    def house(self):
        raise self.error

    def wheel_image(self, for_py_version, name):
        raise self.error

    def py_info_clear(self):
        """nothing to clear"""


class ContentStoreNA(ContentStore):
    def exists(self):
        return False

    def read(self):
        """nothing to read"""
        return None

    def write(self, content):
        """nothing to write"""

    def remove(self):
        """nothing to remove"""

    @contextmanager
    def locked(self):
        yield


__all__ = [
    "AppDataDisabled",
    "ContentStoreNA",
]
