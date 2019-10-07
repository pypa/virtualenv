from __future__ import absolute_import, unicode_literals

from .cpython2 import CPython2Posix, CPython2Windows
from .cpython3 import CPython3Posix, CPython3Windows


def select(interpreter):
    """select the correct creator for the given CPython interpreter"""
    if interpreter.version_info.major == 2:
        if interpreter.os == "nt":
            return CPython2Windows
        return CPython2Posix
    else:
        if interpreter.os == "nt":
            return CPython3Windows
        return CPython3Posix
