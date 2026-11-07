from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING, NamedTuple

import pytest
from python_discovery import PythonInfo
from testing import path
from testing.py_info import read_fixture

if TYPE_CHECKING:
    from pytest_mock import MockerFixture

    from tests.types import Interpreter, MakeInterpreter

# Allows to import from `testing` into test submodules.
sys.path.append(str(Path(__file__).parent))


class _VersionInfo(NamedTuple):
    major: int
    minor: int


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
def make_interpreter(mocker: MockerFixture) -> MakeInterpreter:
    def _make(
        sysconfig_vars: dict[str, object] | None = None,
        prefix: str = "/usr",
        free_threaded: bool = False,
        version_info: tuple[int, ...] = (3, 14, 0),
    ) -> Interpreter:
        return mocker.create_autospec(
            PythonInfo,
            instance=True,
            prefix=prefix,
            system_prefix=prefix,
            system_executable=f"{prefix}/bin/python3",
            free_threaded=free_threaded,
            version_info=_VersionInfo(major=version_info[0], minor=version_info[1]),
            sysconfig_vars=sysconfig_vars or {},
        )

    return _make  # type: ignore[return-value]  # autospec PythonInfo is not an Interpreter to ty
