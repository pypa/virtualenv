from __future__ import absolute_import, unicode_literals

import os
from abc import ABCMeta, abstractmethod
from collections import OrderedDict
from stat import S_IXGRP, S_IXOTH, S_IXUSR

from six import add_metaclass, ensure_text

from virtualenv.info import PY3, fs_is_case_sensitive, fs_supports_symlink
from virtualenv.util.path import copy, link, make_exe, symlink


@add_metaclass(ABCMeta)
class PathRef(object):
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


@add_metaclass(ABCMeta)
class ExePathRef(PathRef):
    def __init__(self, src):
        super(ExePathRef, self).__init__(src)
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


class PathRefToDest(PathRef):
    def __init__(self, src, dest):
        super(PathRefToDest, self).__init__(src)
        self.dest = dest

    def run(self, creator, symlinks):
        dest = self.dest(creator, self.src)
        method = symlink if symlinks else copy
        dest_iterable = dest if isinstance(dest, list) else (dest,)
        for dst in dest_iterable:
            method(self.src, dst)


alias_via = link if PY3 else (symlink if PathRef.FS_SUPPORTS_SYMLINK else copy)


class ExePathRefToDest(PathRefToDest, ExePathRef):
    def __init__(self, src, targets, dest, must_copy=False):
        ExePathRef.__init__(self, src)
        PathRefToDest.__init__(self, src, dest)
        if not self.FS_CASE_SENSITIVE:
            targets = list(OrderedDict((i.lower(), None) for i in targets).keys())
        self.base = targets[0]
        self.aliases = targets[1:]
        self.dest = dest
        self.must_copy = must_copy

    def run(self, creator, symlinks):
        bin_dir = self.dest(creator, self.src).parent
        method = symlink if self.must_copy is False and symlinks else copy
        dest = bin_dir / self.base
        method(self.src, dest)
        make_exe(dest)
        for extra in self.aliases:
            link_file = bin_dir / extra
            if link_file.exists():
                link_file.unlink()
            alias_via(dest, link_file)
            make_exe(link_file)
