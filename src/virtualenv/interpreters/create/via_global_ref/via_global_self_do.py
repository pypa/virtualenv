from __future__ import absolute_import, unicode_literals

import abc
from abc import ABCMeta
from collections import OrderedDict
from os import chmod, stat
from stat import S_IXGRP, S_IXOTH, S_IXUSR

import six
from six import add_metaclass

from virtualenv.info import is_fs_case_sensitive
from virtualenv.interpreters.create.builtin_way import VirtualenvBuiltin
from virtualenv.util.path import Path, copy, ensure_dir, symlink


@add_metaclass(ABCMeta)
class ViaGlobalRefVirtualenvBuiltin(VirtualenvBuiltin):
    def __init__(self, options, interpreter):
        super(ViaGlobalRefVirtualenvBuiltin, self).__init__(options, interpreter)
        self.copier = symlink if self.symlinks is True else copy

    def create(self):
        for directory in sorted(self.ensure_directories()):
            ensure_dir(directory)
        self.set_pyenv_cfg()
        self.pyenv_cfg.write()
        true_system_site = self.enable_system_site_package
        try:
            self.enable_system_site_package = False
            self.setup_python()
        finally:
            if true_system_site != self.enable_system_site_package:
                self.enable_system_site_package = true_system_site

    def set_pyenv_cfg(self):
        """
        We directly inject the base prefix and base exec prefix to avoid site.py needing to discover these
        from home (which usually is done within the interpreter itself)
         """
        super(ViaGlobalRefVirtualenvBuiltin, self).set_pyenv_cfg()
        self.pyenv_cfg["base-prefix"] = self.interpreter.system_prefix
        self.pyenv_cfg["base-exec-prefix"] = self.interpreter.system_exec_prefix
        self.pyenv_cfg["base-executable"] = self.interpreter.system_executable

    def ensure_directories(self):
        dirs = {self.dest_dir, self.bin_dir, self.lib_dir}
        dirs.update(self.site_packages)
        return dirs

    def setup_python(self):
        aliases = method = self.add_exe_method()
        if six.PY3:
            from os import link

            def do_link(src, dst):
                link(six.ensure_text(str(src)), six.ensure_text(str(dst)))

            aliases = do_link
        for src, targets in self.link_exe().items():
            if not is_fs_case_sensitive():
                targets = list(OrderedDict((i.lower(), None) for i in targets).keys())
            to = self.bin_dir / targets[0]
            method(src, to)
            for extra in targets[1:]:
                link_file = self.bin_dir / extra
                if link_file.exists():
                    link_file.unlink()
                aliases(to, link_file)

    def add_exe_method(self):
        if self.copier is symlink:
            return self.symlink_exe
        return self.copier

    @abc.abstractmethod
    def link_exe(self):
        raise NotImplementedError

    @staticmethod
    def symlink_exe(src, dest):
        symlink(src, dest)
        dest_str = six.ensure_text(str(dest))
        original_mode = stat(dest_str).st_mode
        chmod(dest_str, original_mode | S_IXUSR | S_IXGRP | S_IXOTH)

    @property
    def lib_base(self):
        raise NotImplementedError

    @property
    def system_stdlib(self):
        return Path(self.interpreter.system_prefix) / self.lib_base

    @property
    def lib_dir(self):
        return self.dest_dir / self.lib_base

    @abc.abstractmethod
    def lib_name(self):
        raise NotImplementedError
