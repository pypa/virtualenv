from __future__ import annotations

import sys
from uuid import uuid4

import pytest

from virtualenv.cache import FileCache
from virtualenv.discovery.py_info import PythonInfo
from virtualenv.run import cli_run


@pytest.mark.slow
def test_failed_to_find_bad_spec():
    of_id = uuid4().hex
    with pytest.raises(RuntimeError) as context:
        cli_run(["-p", of_id])
    msg = repr(RuntimeError(f"failed to find interpreter for Builtin discover of python_spec={of_id!r}"))
    assert repr(context.value) == msg


def test_failed_to_find_implementation(mocker, session_app_data):
    cache = FileCache(session_app_data.py_info, session_app_data.py_info_clear)
    system = PythonInfo.current_system(session_app_data, cache)
    of_ids = ({sys.executable} if sys.executable != system.executable else set()) | {system.implementation}
    for of_id in of_ids:
        mocker.patch("virtualenv.run.plugin.creators.CreatorSelector._OPTIONS", return_value={})
        with pytest.raises(RuntimeError) as context:
            cli_run(["-p", of_id])
        assert repr(context.value) == repr(
            RuntimeError(f"No virtualenv implementation for {PythonInfo.current_system(session_app_data, cache)}"),
        )
