from __future__ import absolute_import, unicode_literals

import logging
from copy import copy

from virtualenv.error import ProcessCallFailed
from virtualenv.interpreters.discovery.py_info import CURRENT
from virtualenv.util.subprocess import run_cmd

from .via_global_ref import ViaGlobalRef


class Venv(ViaGlobalRef):
    def __init__(self, options, interpreter):
        super(Venv, self).__init__(options, interpreter)
        self.can_be_inline = interpreter is CURRENT and interpreter.executable == interpreter.system_executable
        self._context = None

    @classmethod
    def supports(cls, interpreter):
        return interpreter.has_venv

    def create(self):
        if self.can_be_inline:
            self.create_inline()
        else:
            self.create_via_sub_process()
            # TODO: cleanup activation scripts

    def create_inline(self):
        from venv import EnvBuilder

        builder = EnvBuilder(
            system_site_packages=self.system_site_package,
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
        if self.system_site_package:
            cmd.append("--system-site-packages")
        cmd.append("--symlinks" if self.symlinks else "--copies")
        cmd.append(str(self.dest_dir))
        return cmd

    def set_pyenv_cfg(self):
        # prefer venv options over ours, but keep our extra
        venv_content = copy(self.pyenv_cfg.refresh())
        super(Venv, self).set_pyenv_cfg()
        self.pyenv_cfg.update(venv_content)

    @property
    def bin_name(self):
        return "Scripts" if self.interpreter.os == "nt" else "bin"

    @property
    def lib_dir(self):
        base = self.dest_dir / ("Lib" if self.interpreter.os == "nt" else "lib")
        if self.interpreter.os != "nt":
            base = base / self.interpreter.python_name
        return base
