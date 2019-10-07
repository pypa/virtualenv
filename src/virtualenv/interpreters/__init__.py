from __future__ import absolute_import, unicode_literals

from .create.impl.cpython.selector import select as select_c_python
from .create.impl.pypy import PyPy
from .discovery import get_interpreter

InterpreterTypes = {"CPython": select_c_python, "PyPy": PyPy}


def get_creator_with_interpreter(string_spec):
    interpreter = get_interpreter(string_spec)
    if interpreter is None:
        raise RuntimeError("failed to find interpreter for spec {}".format(string_spec))
    creator_class = InterpreterTypes.get(interpreter.implementation)
    if creator_class is None:
        raise RuntimeError("No virtualenv implementation for {}".format(interpreter.implementation))
    if callable(creator_class):
        creator_class = creator_class(interpreter)
    return creator_class, interpreter
