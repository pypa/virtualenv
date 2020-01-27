from __future__ import absolute_import, unicode_literals

import logging
from abc import ABCMeta
from collections import namedtuple

from six import add_metaclass

from virtualenv.create.via_global_ref.builtin.ref import ExePathRefToDest
from virtualenv.info import fs_supports_symlink
from virtualenv.util.path import ensure_dir

from ..api import ViaGlobalRefApi
from .builtin_way import VirtualenvBuiltin

Meta = namedtuple("Meta", ["sources", "can_copy", "can_symlink"])


@add_metaclass(ABCMeta)
class ViaGlobalRefVirtualenvBuiltin(ViaGlobalRefApi, VirtualenvBuiltin):
    def __init__(self, options, interpreter):
        super(ViaGlobalRefVirtualenvBuiltin, self).__init__(options, interpreter)
        self._sources = getattr(options.meta, "sources", None)  # if we're created as a describer this might be missing

    @classmethod
    def can_create(cls, interpreter):
        """By default all built-in methods assume that if we can describe it we can create it"""
        # first we must be able to describe it
        if cls.can_describe(interpreter):
            sources = []
            can_copy = True
            can_symlink = fs_supports_symlink()
            for src in cls.sources(interpreter):
                if src.exists:
                    if can_copy and not src.can_copy:
                        can_copy = False
                        logging.debug("%s cannot copy %s", cls.__name__, src)
                    if can_symlink and not src.can_symlink:
                        can_symlink = False
                        logging.debug("%s cannot symlink %s", cls.__name__, src)
                    if not (can_copy or can_symlink):
                        break
                else:
                    logging.debug("%s missing %s", cls.__name__, src)
                    break
                sources.append(src)
            else:
                return Meta(sources, can_copy, can_symlink)
        return None

    @classmethod
    def sources(cls, interpreter):
        is_py2 = interpreter.version_info.major == 2
        for host_exe, targets in cls._executables(interpreter):
            yield ExePathRefToDest(host_exe, dest=cls.to_bin, targets=targets, must_copy=is_py2)

    def to_bin(self, src):
        return self.bin_dir / src.name

    @classmethod
    def _executables(cls, interpreter):
        raise NotImplementedError

    def create(self):
        dirs = self.ensure_directories()
        for directory in list(dirs):
            if any(i for i in dirs if i is not directory and directory.parts == i.parts[: len(directory.parts)]):
                dirs.remove(directory)
        for directory in sorted(dirs):
            ensure_dir(directory)

        self.set_pyenv_cfg()
        self.pyenv_cfg.write()
        true_system_site = self.enable_system_site_package
        try:
            self.enable_system_site_package = False
            for src in self._sources:
                src.run(self, self.symlinks)
        finally:
            if true_system_site != self.enable_system_site_package:
                self.enable_system_site_package = true_system_site

    def ensure_directories(self):
        return {self.dest, self.bin_dir, self.script_dir, self.stdlib} | set(self.libs)

    def set_pyenv_cfg(self):
        """
        We directly inject the base prefix and base exec prefix to avoid site.py needing to discover these
        from home (which usually is done within the interpreter itself)
         """
        super(ViaGlobalRefVirtualenvBuiltin, self).set_pyenv_cfg()
        self.pyenv_cfg["base-prefix"] = self.interpreter.system_prefix
        self.pyenv_cfg["base-exec-prefix"] = self.interpreter.system_exec_prefix
        self.pyenv_cfg["base-executable"] = self.interpreter.system_executable
