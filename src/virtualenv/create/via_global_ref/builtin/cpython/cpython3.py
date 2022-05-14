from __future__ import absolute_import, unicode_literals

import abc
import re
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
        for src in super(CPython3Windows, cls).sources(interpreter):
            yield src
        if not cls.has_shim(interpreter):
            for src in cls.include_dll_and_pyd(interpreter):
                yield src
            python_zip = WindowsPythonZipRef(cls, interpreter)
            if python_zip.exists:
                yield python_zip

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
    def include_dll_and_pyd(cls, interpreter):
        dll_folder = Path(interpreter.system_prefix) / "DLLs"
        host_exe_folder = Path(interpreter.system_executable).parent
        for folder in [host_exe_folder, dll_folder]:
            for file in folder.iterdir():
                if file.suffix in (".pyd", ".dll"):
                    yield PathRefToDest(file, dest=cls.to_bin)


class WindowsPythonZipRef(PathRefToDest):
    def __init__(self, creator, interpreter):
        super().__init__(Path(windows_python_zip(interpreter)), creator.to_bin)


def windows_python_zip(interpreter):
    """
    This is a path to the "python<VERSION>.zip", which contains the compiled
    *.pyc packages from the Python std lib.
    :see: https://docs.python.org/3/using/windows.html#the-embeddable-package

    The <VERSION> is the `py_version_nodot` var from the `sysconfig` module.
    For example, for the Python 3.10 the `py_version_nodot` would be "310" and
    the `python_zip` value should be "python310.zip".
    :see: `python -m sysconfig` output.
    :see: `discovery.py_info.PythonInfo` class (interpreter).

    :note: By default, the embeddable Python distribution for Windows includes
    the "python<VERSION>.zip" and the "python<VERSION>._pth" files in the
    Python bin dir. User can move/rename *zip* file and edit `sys.path` by
    editing *_pth* file. This function can only recognize the std name of the
    embeddable *zip* file!

    :return: (str) first matched `python_zip_path` or `python_zip` file name.
    :note: Don't return an empty str, because it will be turned into an
    existing current path `.` and will cause a recursion err.
    """
    python_zip = "python{}.zip".format(interpreter.version_nodot)
    # Any str ends with `python_zip` file name.
    python_zip_path = ".*{}$".format(python_zip)
    path_re = re.compile(python_zip_path, re.IGNORECASE)
    path_matches = filter(None, map(path_re.match, interpreter.path))
    # Return first matched `python_zip_path` or `python_zip` file name.
    path_match = next(path_matches, None)
    return path_match.group() if path_match else python_zip
