import abc
import logging
import os
from pathlib import Path

from virtualenv.create.describe import PosixSupports, WindowsSupports
from virtualenv.create.via_global_ref.builtin.ref import PathRefToDest

from ..python2.python2 import Python2
from .common import PyPy


class PyPy2(PyPy, Python2, metaclass=abc.ABCMeta):
    """PyPy 2"""

    @classmethod
    def exe_stem(cls):
        return "pypy"

    @classmethod
    def sources(cls, interpreter):
        yield from super().sources(interpreter)
        # include folder needed on Python 2 as we don't have pyenv.cfg
        host_include_marker = cls.host_include_marker(interpreter)
        if host_include_marker.exists():
            yield PathRefToDest(host_include_marker.parent, dest=lambda self, _: self.include)  # noqa: U101

    @classmethod
    def needs_stdlib_py_module(cls):
        return True

    @classmethod
    def host_include_marker(cls, interpreter):
        return Path(interpreter.system_include) / "PyPy.h"

    @property
    def include(self):
        return self.dest / self.interpreter.install_path("headers")

    @classmethod
    def modules(cls):
        # pypy2 uses some modules before the site.py loads, so we need to include these too
        return super().modules() + [
            "os",
            "copy_reg",
            "genericpath",
            "linecache",
            "stat",
            "UserDict",
            "warnings",
        ]

    @property
    def lib_pypy(self):
        return self.dest / "lib_pypy"

    def ensure_directories(self):
        dirs = super().ensure_directories()
        dirs.add(self.lib_pypy)
        host_include_marker = self.host_include_marker(self.interpreter)
        if host_include_marker.exists():
            dirs.add(self.include.parent)
        else:
            logging.debug("no include folders as can't find include marker %s", host_include_marker)
        return dirs

    @property
    def skip_rewrite(self):
        """
        PyPy2 built-in imports are handled by this path entry, don't overwrite to not disable it
        see: https://github.com/pypa/virtualenv/issues/1652
        """
        return f'or path.endswith("lib_pypy{os.sep}__extensions__") # PyPy2 built-in import marker'


class PyPy2Posix(PyPy2, PosixSupports):
    """PyPy 2 on POSIX"""

    @classmethod
    def modules(cls):
        return super().modules() + ["posixpath"]

    @classmethod
    def _shared_libs(cls, python_dir):
        return python_dir.glob("libpypy*.*")

    @property
    def lib(self):
        return self.dest / "lib"

    @classmethod
    def sources(cls, interpreter):
        yield from super().sources(interpreter)
        host_lib = Path(interpreter.system_prefix) / "lib"
        if host_lib.exists():
            yield PathRefToDest(host_lib, dest=lambda self, _: self.lib)  # noqa: U101


class Pypy2Windows(PyPy2, WindowsSupports):
    """PyPy 2 on Windows"""

    @classmethod
    def modules(cls):
        return super().modules() + ["ntpath"]

    @classmethod
    def _shared_libs(cls, python_dir):
        # No glob in python2 PathLib
        for candidate in ["libpypy-c.dll", "libffi-7.dll", "libffi-8.dll"]:
            dll = python_dir / candidate
            if dll.exists():
                yield dll

    @classmethod
    def sources(cls, interpreter):
        yield from super().sources(interpreter)
        yield PathRefToDest(Path(interpreter.system_prefix) / "libs", dest=lambda self, s: self.dest / s.name)


__all__ = [
    "PyPy2",
    "PyPy2Posix",
    "Pypy2Windows",
]
