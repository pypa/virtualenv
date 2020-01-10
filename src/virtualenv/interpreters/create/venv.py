from __future__ import absolute_import, unicode_literals

import logging
from copy import copy

from virtualenv.error import ProcessCallFailed
from virtualenv.interpreters.discovery.py_info import CURRENT
from virtualenv.util.path import ensure_dir
from virtualenv.util.subprocess import run_cmd

from .via_global_ref.api import ViaGlobalRefApi


class Venv(ViaGlobalRefApi):
    def __init__(self, options, interpreter):
        super(Venv, self).__init__(options, interpreter)
        self.can_be_inline = interpreter is CURRENT and interpreter.executable == interpreter.system_executable
        self._context = None
        self.builtin_way = options.builtin_way

    def _args(self):
        return super(Venv, self)._args() + (
            [("builtin_way", self.builtin_way.__class__.__name__)] if self.builtin_way else []
        )

    @classmethod
    def supports(cls, interpreter):
        return interpreter.has_venv

    def create(self):
        if self.can_be_inline:
            self.create_inline()
        else:
            self.create_via_sub_process()
            # TODO: cleanup activation scripts
        if self.builtin_way is not None:
            for site_package in self.builtin_way.site_packages:
                ensure_dir(site_package)

    def create_inline(self):
        from venv import EnvBuilder

        builder = EnvBuilder(
            system_site_packages=self.enable_system_site_package,
            clear=False,
            symlinks=self.symlinks,
            with_pip=False,
            prompt=None,
        )
        builder.create(self.dest_dir)

    def create_via_sub_process(self):
        cmd = self.get_host_create_cmd()
        logging.info("using host built-in venv to create via %s", " ".join(cmd))
        code, out, err = run_cmd(cmd)
        if code != 0:
            raise ProcessCallFailed(code, out, err, cmd)

    def get_host_create_cmd(self):
        cmd = [self.interpreter.system_executable, "-m", "venv", "--without-pip"]
        if self.enable_system_site_package:
            cmd.append("--system-site-packages")
        cmd.append("--symlinks" if self.symlinks else "--copies")
        cmd.append(str(self.dest_dir))
        return cmd

    def set_pyenv_cfg(self):
        # prefer venv options over ours, but keep our extra
        venv_content = copy(self.pyenv_cfg.refresh())
        super(Venv, self).set_pyenv_cfg()
        self.pyenv_cfg.update(venv_content)

    def _delegate_to_builtin_way(self, key):
        if self.builtin_way is None:
            return None
        return getattr(self.builtin_way, key)

    @property
    def exe(self):
        return self._delegate_to_builtin_way("exe")

    @property
    def site_packages(self):
        return self._delegate_to_builtin_way("site_packages")

    @property
    def bin_dir(self):
        return self._delegate_to_builtin_way("bin_dir")

    @property
    def bin_name(self):
        return self._delegate_to_builtin_way("bin_name")

    @property
    def lib_dir(self):
        return self._delegate_to_builtin_way("lib_dir")
