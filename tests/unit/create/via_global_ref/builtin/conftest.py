from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from testing import path
from testing.py_info import read_fixture

if TYPE_CHECKING:
    from tests.types import Interpreter, MakeInterpreter

# Allows to import from `testing` into test submodules.
sys.path.append(str(Path(__file__).parent))


@pytest.fixture
def py_info(py_info_name):
    return read_fixture(py_info_name)


@pytest.fixture
def mock_files(mocker):
    return lambda paths, files: path.mock_files(mocker, paths, files)


@pytest.fixture
def mock_pypy_libs(mocker):
    return lambda pypy, libs: path.mock_pypy_libs(mocker, pypy, libs)


@pytest.fixture
def make_interpreter() -> MakeInterpreter:
    def _make(
        sysconfig_vars: dict[str, object] | None = None,
        prefix: str = "/usr",
        free_threaded: bool = False,
        version_info: tuple[int, ...] = (3, 14, 0),
    ) -> Interpreter:
        interpreter = MagicMock()
        interpreter.prefix = prefix
        interpreter.system_prefix = prefix
        interpreter.system_executable = f"{prefix}/bin/python3"
        interpreter.free_threaded = free_threaded
        interpreter.version_info = MagicMock(major=version_info[0], minor=version_info[1])
        interpreter.sysconfig_vars = sysconfig_vars or {}
        return interpreter

    return _make  # type: ignore[return-value]
