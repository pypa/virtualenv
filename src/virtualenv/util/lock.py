"""holds locking functionality that works across processes"""
from __future__ import absolute_import, unicode_literals

import logging
from contextlib import contextmanager

from filelock import FileLock, Timeout

from virtualenv.util.path import Path, ensure_dir


class FSLock(object):
    def __init__(self, folder):
        self.path = Path(folder)
        self._lock = self._make_lock()

    def __enter__(self):
        self._lock_file(self._lock)

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._release(self._lock)

    @contextmanager
    def lock_for_key(self, name):
        lock = self._make_lock(name)
        try:
            self._lock_file(lock)
            yield
        finally:
            self._release(lock)

    def _lock_file(self, lock):
        ensure_dir(self.path)
        try:
            lock.acquire(0.0001)
        except Timeout:
            logging.debug("lock file %s present, will block until released", self._lock.lock_file)
            lock.acquire()

    def _make_lock(self, name=""):
        return FileLock(str(self.path / "{}.lock".format(name)))

    @staticmethod
    def _release(lock):
        lock.release()

    def __div__(self, other):
        return FSLock(self.path / other)

    def __truediv__(self, other):
        return self.__div__(other)

    def __repr__(self):
        return "{}({})".format(self.__class__.__name__, self.path)
