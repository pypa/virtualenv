from __future__ import absolute_import, unicode_literals

import os
import sys
from uuid import uuid4

import pytest

from virtualenv.interpreters.discovery.builtin import get_interpreter
from virtualenv.interpreters.discovery.py_info import CURRENT


@pytest.mark.skipif(sys.platform == "win32", reason="symlink is not guaranteed to work on windows")
@pytest.mark.parametrize("case", ["mixed", "lower", "upper"])
def test_discovery_via_path(tmp_path, monkeypatch, case):
    core = "somethingVeryCryptic{}".format(".".join(str(i) for i in CURRENT.version_info[0:3]))
    name = "somethingVeryCryptic"
    if case == "lower":
        name = name.lower()
    elif case == "upper":
        name = name.upper()
    exe_name = "{}{}{}".format(name, CURRENT.version_info.major, ".exe" if sys.platform == "win32" else "")
    executable = tmp_path / exe_name
    os.symlink(sys.executable, str(executable))
    new_path = os.pathsep.join([str(tmp_path)] + os.environ.get(str("PATH"), str("")).split(os.pathsep))
    monkeypatch.setenv(str("PATH"), new_path)
    interpreter = get_interpreter(core)

    assert interpreter is not None


def test_discovery_via_path_not_found():
    interpreter = get_interpreter(uuid4().hex)
    assert interpreter is None
