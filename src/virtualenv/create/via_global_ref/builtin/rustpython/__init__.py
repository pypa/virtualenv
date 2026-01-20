from __future__ import annotations

from virtualenv.create.via_global_ref.builtin.cpython.cpython3 import CPython3Posix


class RustPythonPosix(CPython3Posix):
    """
    Creator for RustPython.

    RustPython is mostly compatible with CPython3,
    so we can reuse cpython creator code.
    """

    @classmethod
    def can_describe(cls, interpreter):
        return interpreter.implementation == "RustPython"
