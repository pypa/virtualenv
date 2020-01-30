from __future__ import absolute_import, unicode_literals

import logging
from collections import namedtuple
from copy import copy

from virtualenv.discovery.py_info import PythonInfo
from virtualenv.error import ProcessCallFailed
from virtualenv.info import fs_supports_symlink
from virtualenv.util.path import ensure_dir
from virtualenv.util.subprocess import run_cmd

from .api import ViaGlobalRefApi

Meta = namedtuple("Meta", ["can_symlink", "can_copy"])


class Venv(ViaGlobalRefApi):
    def __init__(self, options, interpreter):
        self.describe = options.describe
        super(Venv, self).__init__(options, interpreter)
        self.can_be_inline = (
            interpreter is PythonInfo.current() and interpreter.executable == interpreter.system_executable
        )
        self._context = None

    def _args(self):
        return super(Venv, self)._args() + ([("describe", self.describe.__class__.__name__)] if self.describe else [])

    @classmethod
    def can_create(cls, interpreter):
        if interpreter.has_venv:
            return Meta(can_symlink=fs_supports_symlink(), can_copy=True)
        return None

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
        builder.create(str(self.dest))

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
        cmd.append(str(self.dest))
        return cmd

    def set_pyenv_cfg(self):
        # prefer venv options over ours, but keep our extra
        venv_content = copy(self.pyenv_cfg.refresh())
        super(Venv, self).set_pyenv_cfg()
        self.pyenv_cfg.update(venv_content)

    def __getattribute__(self, item):
        describe = object.__getattribute__(self, "describe")
        if describe is not None and hasattr(describe, item):
            element = getattr(describe, item)
            if not callable(element) or item in ("script",):
                return element
        return object.__getattribute__(self, item)
