from __future__ import absolute_import, unicode_literals

import sys
from uuid import uuid4

import pytest

from virtualenv.interpreters import InterpreterTypes, get_creator_with_interpreter
from virtualenv.interpreters.discovery import CURRENT


def test_failed_to_find_bad_spec():
    of_id = uuid4().hex
    with pytest.raises(RuntimeError) as context:
        get_creator_with_interpreter(of_id)
    assert repr(context.value) == repr(RuntimeError("failed to find interpreter for spec {}".format(of_id)))


@pytest.mark.parametrize("of_id", [sys.executable, CURRENT.implementation])
def test_failed_to_find_implementation(monkeypatch, of_id):
    monkeypatch.delitem(InterpreterTypes, "CPython")
    with pytest.raises(RuntimeError) as context:
        get_creator_with_interpreter(of_id)
    assert repr(context.value) == repr(RuntimeError("No virtualenv implementation for CPython"))
