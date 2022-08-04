import sys
from uuid import uuid4

import pytest

from virtualenv.discovery.py_info import PythonInfo
from virtualenv.run import cli_run


@pytest.mark.slow()
def test_failed_to_find_bad_spec():
    of_id = uuid4().hex
    with pytest.raises(RuntimeError) as context:
        cli_run(["-p", of_id])
    msg = repr(RuntimeError(f"failed to find interpreter for Builtin discover of python_spec={of_id!r}"))
    assert repr(context.value) == msg


SYSTEM = PythonInfo.current_system()


@pytest.mark.parametrize(
    "of_id",
    ({sys.executable} if sys.executable != SYSTEM.executable else set()) | {SYSTEM.implementation},
)
def test_failed_to_find_implementation(of_id, mocker):
    mocker.patch("virtualenv.run.plugin.creators.CreatorSelector._OPTIONS", return_value={})
    with pytest.raises(RuntimeError) as context:
        cli_run(["-p", of_id])
    assert repr(context.value) == repr(RuntimeError(f"No virtualenv implementation for {PythonInfo.current_system()}"))
