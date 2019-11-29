from __future__ import absolute_import, unicode_literals

import sys
from uuid import uuid4

import pytest

from virtualenv.interpreters.discovery.py_info import CURRENT
from virtualenv.run import run_via_cli


def test_failed_to_find_bad_spec():
    of_id = uuid4().hex
    with pytest.raises(RuntimeError) as context:
        run_via_cli(["-p", of_id])
    msg = repr(RuntimeError("failed to find interpreter for Builtin discover of python_spec={!r}".format(of_id)))
    assert repr(context.value) == msg


@pytest.mark.parametrize("of_id", [sys.executable, CURRENT.implementation])
def test_failed_to_find_implementation(of_id, mocker):
    mocker.patch("virtualenv.run._collect_creators", return_value={})
    with pytest.raises(RuntimeError) as context:
        run_via_cli(["-p", of_id])
    assert repr(context.value) == repr(RuntimeError("No virtualenv implementation for {}".format(CURRENT)))
