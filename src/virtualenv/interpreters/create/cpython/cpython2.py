from __future__ import absolute_import, unicode_literals

import abc
from argparse import ArgumentTypeError

import six

from virtualenv.util import Path, copy

from .common import CPython, CPythonPosix, CPythonWindows

HERE = Path(__file__).absolute().parent


@six.add_metaclass(abc.ABCMeta)
class CPython2(CPython):
    """Create a CPython version 2  virtual environment"""

    def set_pyenv_cfg(self):
        """
        We directly inject the base prefix and base exec prefix to avoid site.py needing to discover these
        from home (which usually is done within the interpreter itself)
         """
        super(CPython2, self).set_pyenv_cfg()
        self.pyenv_cfg["base-prefix"] = self.interpreter.system_prefix
        self.pyenv_cfg["base-exec-prefix"] = self.interpreter.system_exec_prefix

    @classmethod
    def supports(cls, interpreter):
        return super(CPython2, cls).supports(interpreter) and interpreter.version_info.major == 2

    def setup_python(self):
        super(CPython2, self).setup_python()  # install the core first
        self.fixup_python2()  # now patch

    def add_exe_method(self):
        return copy

    def fixup_python2(self):
        """Perform operations needed to make the created environment work on Python 2"""
        # 1. add landmarks for detecting the python home
        self.add_module("os")
        # 2. install a patched site-package, the default Python 2 site.py is not smart enough to understand pyvenv.cfg,
        # so we inject a small shim that can do this
        copy(HERE / "site.py", self.lib_dir / "site.py")

    def add_module(self, req):
        for ext in self.module_extensions:
            file_path = "{}.{}".format(req, ext)
            self.copier(self.system_stdlib / file_path, self.lib_dir / file_path)

    @property
    def module_extensions(self):
        return ["py", "pyc"]


class CPython2Posix(CPython2, CPythonPosix):
    """CPython 2 on POSIX"""

    def fixup_python2(self):
        super(CPython2Posix, self).fixup_python2()
        # linux needs the lib-dynload, these are builtins on Windows
        self.add_folder("lib-dynload")

    def add_folder(self, folder):
        self.copier(self.system_stdlib / folder, self.lib_dir / folder)


class CPython2Windows(CPython2, CPythonWindows):
    """CPython 2 on Windows"""

    @classmethod
    def validate_dest_dir(cls, raw_value):
        # the python prefix discovery mechanism on Windows python 2 uses mbcs - so anything that's not encode-able
        # needs to be refused
        path_converted = raw_value.encode("mbcs", errors="ignore").decode("mbcs")
        if path_converted != raw_value:
            refused = set(raw_value) - {
                c for c, i in ((char, char.encode("mbcs")) for char in raw_value) if c == "?" or i != "?"
            }
            raise ArgumentTypeError(
                "mbcs (path encoder for CPython2.7 on Windows) does not support characters %r".format(refused)
            )
        return super(CPython2Windows, cls).validate_dest_dir(raw_value)
