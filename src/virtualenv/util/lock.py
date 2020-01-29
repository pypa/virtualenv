"""holds locking functionality that works across processes"""
from __future__ import absolute_import, unicode_literals

import logging
import os
from contextlib import contextmanager
from threading import Lock

from filelock import FileLock, Timeout

from virtualenv.util.path import Path


class _CountedFileLock(FileLock):
    def __init__(self, lock_file):
        super(_CountedFileLock, self).__init__(lock_file)
        self.count = 0
        self.thread_safe = Lock()

    def acquire(self, timeout=None, poll_intervall=0.05):
        with self.thread_safe:
            if self.count == 0:
                super(_CountedFileLock, self).acquire(timeout=timeout, poll_intervall=poll_intervall)
            self.count += 1

    def release(self, force=False):
        with self.thread_safe:
            if self.count == 1:
                super(_CountedFileLock, self).release()
            self.count = max(self.count - 1, 0)


class ReentrantFileLock(object):
    def __init__(self, folder):
        self._lock = None
        path = Path(folder)
        self.path = path.resolve() if path.exists() else path

    def __repr__(self):
        return "{}({})".format(self.__class__.__name__, self.path)

    def __div__(self, other):
        return ReentrantFileLock(self.path / other)

    def __truediv__(self, other):
        return self.__div__(other)

    _lock_store = {}
    _store_lock = Lock()

    def _create_lock(self, name=""):
        lock_file = str(self.path / "{}.lock".format(name))
        with self._store_lock:
            if lock_file not in self._lock_store:
                self._lock_store[lock_file] = _CountedFileLock(lock_file)
            return self._lock_store[lock_file]

    def _del_lock(self, lock):
        with self._store_lock:
            if lock is not None:
                with lock.thread_safe:
                    if lock.count == 0:
                        self._lock_store.pop(lock.lock_file)

    def __del__(self):
        self._del_lock(self._lock)

    def __enter__(self):
        self._lock = self._create_lock()
        self._lock_file(self._lock)

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._release(self._lock)

    def _lock_file(self, lock):
        # multiple processes might be trying to get a first lock... so we cannot check if this directory exist without
        # a lock, but that lock might then become expensive, and it's not clear where that lock should live.
        # Instead here we just ignore if we fail to create the directory.
        try:
            os.makedirs(str(self.path))
        except OSError:
            pass
        try:
            lock.acquire(0.0001)
        except Timeout:
            logging.debug("lock file %s present, will block until released", lock.lock_file)
            lock.release()  # release the acquire try from above
            lock.acquire()

    @staticmethod
    def _release(lock):
        lock.release()

    @contextmanager
    def lock_for_key(self, name):
        lock = self._create_lock(name)
        try:
            try:
                self._lock_file(lock)
                yield
            finally:
                self._release(lock)
        finally:
            self._del_lock(lock)
