from __future__ import annotations

from virtualenv.create.via_global_ref.builtin.rustpython import RustPythonPosix
from virtualenv.discovery.py_info import PythonInfo


def test_can_describe():
    """
    Test RustPythonPosix.can_describe() class method.
    """
    interpreter = PythonInfo()

    # check that RustPython implementation is supported
    interpreter.implementation = "RustPython"
    assert RustPythonPosix.can_describe(interpreter)

    # check that non-RustPython implementation is not supported
    interpreter.implementation = "CPython"
    assert not RustPythonPosix.can_describe(interpreter)
