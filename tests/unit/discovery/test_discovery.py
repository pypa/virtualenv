from __future__ import absolute_import, unicode_literals

import logging
import os
import sys
from uuid import uuid4

import pytest
import six

from virtualenv.discovery.builtin import get_interpreter
from virtualenv.discovery.py_info import PythonInfo
from virtualenv.info import fs_supports_symlink


@pytest.mark.skipif(not fs_supports_symlink(), reason="symlink not supported")
@pytest.mark.parametrize("case", ["mixed", "lower", "upper"])
def test_discovery_via_path(monkeypatch, case, special_name_dir, caplog):
    caplog.set_level(logging.DEBUG)
    current = PythonInfo.current_system()
    core = "somethingVeryCryptic{}".format(".".join(str(i) for i in current.version_info[0:3]))
    name = "somethingVeryCryptic"
    if case == "lower":
        name = name.lower()
    elif case == "upper":
        name = name.upper()
    exe_name = "{}{}{}".format(name, current.version_info.major, ".exe" if sys.platform == "win32" else "")
    special_name_dir.mkdir()
    executable = special_name_dir / exe_name
    os.symlink(sys.executable, six.ensure_text(str(executable)))
    new_path = os.pathsep.join([str(special_name_dir)] + os.environ.get(str("PATH"), str("")).split(os.pathsep))
    monkeypatch.setenv(str("PATH"), new_path)
    interpreter = get_interpreter(core)

    assert interpreter is not None


def test_discovery_via_path_not_found(tmp_path, monkeypatch):
    monkeypatch.setenv(str("PATH"), str(tmp_path))
    interpreter = get_interpreter(uuid4().hex)
    assert interpreter is None
