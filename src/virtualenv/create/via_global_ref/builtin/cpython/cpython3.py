from __future__ import absolute_import, unicode_literals

import abc
import fnmatch
from itertools import chain
from operator import methodcaller as method
from textwrap import dedent

from six import add_metaclass

from virtualenv.create.describe import Python3Supports
from virtualenv.create.via_global_ref.builtin.ref import PathRefToDest
from virtualenv.create.via_global_ref.store import is_store_python
from virtualenv.util.path import Path

from .common import CPython, CPythonPosix, CPythonWindows, is_mac_os_framework


@add_metaclass(abc.ABCMeta)
class CPython3(CPython, Python3Supports):
    """ """


class CPython3Posix(CPythonPosix, CPython3):
    @classmethod
    def can_describe(cls, interpreter):
        return is_mac_os_framework(interpreter) is False and super(CPython3Posix, cls).can_describe(interpreter)

    def env_patch_text(self):
        text = super(CPython3Posix, self).env_patch_text()
        if self.pyvenv_launch_patch_active(self.interpreter):
            text += dedent(
                """
                # for https://github.com/python/cpython/pull/9516, see https://github.com/pypa/virtualenv/issues/1704
                import os
                if "__PYVENV_LAUNCHER__" in os.environ:
                    del os.environ["__PYVENV_LAUNCHER__"]
                """,
            )
        return text

    @classmethod
    def pyvenv_launch_patch_active(cls, interpreter):
        ver = interpreter.version_info
        return interpreter.platform == "darwin" and ((3, 7, 8) > ver >= (3, 7) or (3, 8, 3) > ver >= (3, 8))


class CPython3Windows(CPythonWindows, CPython3):
    """ """

    @classmethod
    def setup_meta(cls, interpreter):
        if is_store_python(interpreter):  # store python is not supported here
            return None
        return super(CPython3Windows, cls).setup_meta(interpreter)

    @classmethod
    def sources(cls, interpreter):
        if cls.has_shim(interpreter):
            refs = cls.executables(interpreter)
        else:
            refs = chain(
                cls.executables(interpreter),
                cls.dll_and_pyd(interpreter),
                cls.python_zip(interpreter),
            )
        for ref in refs:
            yield ref

    @classmethod
    def executables(cls, interpreter):
        return super(CPython3Windows, cls).sources(interpreter)

    @classmethod
    def has_shim(cls, interpreter):
        return interpreter.version_info.minor >= 7 and cls.shim(interpreter) is not None

    @classmethod
    def shim(cls, interpreter):
        shim = Path(interpreter.system_stdlib) / "venv" / "scripts" / "nt" / "python.exe"
        if shim.exists():
            return shim
        return None

    @classmethod
    def host_python(cls, interpreter):
        if cls.has_shim(interpreter):
            # starting with CPython 3.7 Windows ships with a venvlauncher.exe that avoids the need for dll/pyd copies
            # it also means the wrapper must be copied to avoid bugs such as https://bugs.python.org/issue42013
            return cls.shim(interpreter)
        return super(CPython3Windows, cls).host_python(interpreter)

    @classmethod
    def dll_and_pyd(cls, interpreter):
        dll_folder = Path(interpreter.system_prefix) / "DLLs"
        host_exe_folder = Path(interpreter.system_executable).parent
        for folder in [host_exe_folder, dll_folder]:
            for file in folder.iterdir():
                if file.suffix in (".pyd", ".dll"):
                    yield PathRefToDest(file, cls.to_bin)

    @classmethod
    def python_zip(cls, interpreter):
        """
        "python{VERSION}.zip" contains compiled *.pyc std lib packages, where
        "VERSION" is `py_version_nodot` var from the `sysconfig` module.
        :see: https://docs.python.org/3/using/windows.html#the-embeddable-package
        :see: `discovery.py_info.PythonInfo` class (interpreter).
        :see: `python -m sysconfig` output.

        :note: The embeddable Python distribution for Windows includes
        "python{VERSION}.zip" and "python{VERSION}._pth" files. User can
        move/rename *zip* file and edit `sys.path` by editing *_pth* file.
        Here the `pattern` is used only for the default *zip* file name!
        """
        pattern = "*python{}.zip".format(interpreter.version_nodot)
        matches = fnmatch.filter(interpreter.path, pattern)
        matched_paths = map(Path, matches)
        existing_paths = filter(method("exists"), matched_paths)
        path = next(existing_paths, None)
        if path is not None:
            yield PathRefToDest(path, cls.to_bin)
