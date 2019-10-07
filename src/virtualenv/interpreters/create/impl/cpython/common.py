from __future__ import absolute_import, unicode_literals

import abc
from os import X_OK, access, chmod

import six
from pathlib2 import Path

from virtualenv.interpreters.create.api import Creator
from virtualenv.util import symlink


@six.add_metaclass(abc.ABCMeta)
class CPython(Creator):
    @abc.abstractmethod
    def lib_name(self):
        raise NotImplementedError

    @property
    def lib_base(self):
        raise NotImplementedError

    @property
    def lib_dir(self):
        return self.env_dir / self.lib_base

    @property
    def system_stdlib(self):
        return Path(self.interpreter.system_prefix) / self.lib_base

    def exe_names(self):
        yield Path(self.interpreter.system_executable).name

    def add_exe_method(self):
        if self.copier is symlink:
            return self.symlink_exe
        return self.copier

    def symlink_exe(self, src, dest):
        symlink(src, dest)
        dest_str = str(dest)
        if not access(dest_str, X_OK):
            chmod(dest_str, 0o755)  # pragma: no cover

    def setup_python(self):
        super(CPython, self).setup_python()
        python_dir = Path(self.interpreter.system_executable).parent
        for name in self.exe_names():
            self.add_executable(python_dir, self.bin_dir, name)

    def add_executable(self, src, dest, name):
        src_ex = src / name
        if src_ex.exists():
            add_exe_method_ = self.add_exe_method()
            add_exe_method_(src_ex, dest / name)


@six.add_metaclass(abc.ABCMeta)
class CPythonPosix(CPython):
    """Create a CPython virtual environment on POSIX platforms"""

    @property
    def bin_name(self):
        return "bin"

    @property
    def lib_name(self):
        return "lib"

    @property
    def lib_base(self):
        return Path(self.lib_name) / self.python_name

    def setup_python(self):
        """Just create an exe in the provisioned virtual environment skeleton directory"""
        super(CPythonPosix, self).setup_python()
        major, minor = self.interpreter.version_info.major, self.interpreter.version_info.minor
        target = self.bin_dir / next(self.exe_names())
        for suffix in ("python", "python{}".format(major), "python{}.{}".format(major, minor)):
            path = self.bin_dir / suffix
            if not path.exists():
                symlink(target, path, relative_symlinks_ok=True)


@six.add_metaclass(abc.ABCMeta)
class CPythonWindows(CPython):
    @property
    def bin_name(self):
        return "Scripts"

    @property
    def lib_name(self):
        return "Lib"

    @property
    def lib_base(self):
        return Path(self.lib_name)

    def exe_names(self):
        yield Path(self.interpreter.system_executable).name
        for name in ["python", "pythonw"]:
            for suffix in ["exe"]:
                yield "{}.{}".format(name, suffix)
