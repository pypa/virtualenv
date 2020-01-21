from __future__ import absolute_import, unicode_literals

import logging
import os
from abc import ABCMeta, abstractmethod
from collections import OrderedDict
from stat import S_IXGRP, S_IXOTH, S_IXUSR

from six import add_metaclass, ensure_text

from virtualenv.info import PY3, fs_is_case_sensitive, fs_supports_symlink
from virtualenv.util.path import copy, make_exe, symlink

if PY3:
    from os import link


@add_metaclass(ABCMeta)
class Ref(object):
    FS_SUPPORTS_SYMLINK = fs_supports_symlink()
    FS_CASE_SENSITIVE = fs_is_case_sensitive()

    def __init__(self, src):
        self.src = src
        self.exists = src.exists()
        self._can_read = None if self.exists else False
        self._can_copy = None if self.exists else False
        self._can_symlink = None if self.exists else False

    def __repr__(self):
        return "{}(src={})".format(self.__class__.__name__, self.src)

    @property
    def can_read(self):
        if self._can_read is None:
            if self.src.is_file():
                try:
                    with self.src.open("rb"):
                        self._can_read = True
                except OSError:
                    self._can_read = False
            else:
                self._can_read = os.access(ensure_text(str(self.src)), os.R_OK)
        return self._can_read

    @property
    def can_copy(self):
        if self._can_copy is None:
            self._can_copy = self.can_read
        return self._can_copy

    @property
    def can_symlink(self):
        if self._can_symlink is None:
            self._can_symlink = self.FS_SUPPORTS_SYMLINK and self.can_read
        return self._can_symlink

    @abstractmethod
    def run(self, creator, symlinks):
        raise NotImplementedError

    def method(self, via_symlink):
        pass


@add_metaclass(ABCMeta)
class ExeRef(Ref):
    def __init__(self, src):
        super(ExeRef, self).__init__(src)
        self._can_run = None

    @property
    def can_symlink(self):
        if self.FS_SUPPORTS_SYMLINK:
            return self.can_run
        return False

    @property
    def can_run(self):
        if self._can_run is None:
            mode = self.src.stat().st_mode
            for key in [S_IXUSR, S_IXGRP, S_IXOTH]:
                if mode & key:
                    self._can_run = True
                break
            else:
                self._can_run = False
        return self._can_run


class RefToDest(Ref):
    def __init__(self, src, dest):
        super(RefToDest, self).__init__(src)
        self.dest = dest

    def run(self, creator, method):
        dest = self.dest(creator, self.src)
        if not isinstance(dest, list):
            dest = [dest]
        for dst in dest:
            method(self.src, dst)


class ExeRefToDest(ExeRef):
    def __init__(self, src, targets, dest, must_copy=False):
        super(ExeRefToDest, self).__init__(src)
        if not self.FS_CASE_SENSITIVE:
            targets = list(OrderedDict((i.lower(), None) for i in targets).keys())
        self.base = targets[0]
        self.aliases = targets[1:]
        self.dest = dest
        self.must_copy = must_copy

    def run(self, creator, method):
        to = self.dest(creator, self.src).parent
        dest = to / self.base
        if self.must_copy:
            method = copy
        method(self.src, dest)
        make_exe(dest)

        for extra in self.aliases:
            link_file = to / extra
            if link_file.exists():
                link_file.unlink()
            self.alias_via(dest, link_file)
            make_exe(link_file)

    @staticmethod
    def do_link(src, dst):
        logging.debug("hard link %s as %s", dst.name, src)
        link(ensure_text(str(src)), ensure_text(str(dst)))

    alias_via = do_link if PY3 else (symlink if Ref.FS_SUPPORTS_SYMLINK else copy)
