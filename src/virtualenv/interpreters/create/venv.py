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
        self.builtin_way = options.builtin_way
        super(Venv, self).__init__(options, interpreter)
        self.can_be_inline = interpreter is CURRENT and interpreter.executable == interpreter.system_executable
        self._context = None

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
        for lib in self.libs:
            ensure_dir(lib)

    def create_inline(self):
        from venv import EnvBuilder

        builder = EnvBuilder(
            system_site_packages=self.enable_system_site_package, clear=False, symlinks=self.symlinks, with_pip=False,
        )
        builder.create(str(self.dest_dir))

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

    def __getattribute__(self, item):
        builtin = object.__getattribute__(self, "builtin_way")
        if builtin is not None and hasattr(builtin, item):
            element = getattr(builtin, item)
            if not callable(element):
                return element
        return object.__getattribute__(self, item)
