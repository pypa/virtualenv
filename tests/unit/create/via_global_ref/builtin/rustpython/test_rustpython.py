from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from testing.helpers import contains_exe

from virtualenv.create.via_global_ref.builtin.rustpython import RustPythonPosix, RustPythonWindows


@pytest.mark.parametrize("py_info_name", ["rustpython_posix"])
def test_can_describe_rustpython_posix(py_info: MagicMock) -> None:
    assert RustPythonPosix.can_describe(py_info)


@pytest.mark.parametrize("py_info_name", ["rustpython_windows"])
def test_can_describe_rustpython_windows(py_info: MagicMock) -> None:
    assert RustPythonWindows.can_describe(py_info)


def test_can_describe_rejects_cpython() -> None:
    interpreter = MagicMock()
    interpreter.implementation = "CPython"
    interpreter.os = "posix"
    assert not RustPythonPosix.can_describe(interpreter)
    interpreter.os = "nt"
    assert not RustPythonWindows.can_describe(interpreter)


@pytest.mark.parametrize("py_info_name", ["rustpython_posix"])
def test_sources_posix(py_info: MagicMock, mock_files: object) -> None:
    mock_files(("virtualenv.create.via_global_ref.builtin.rustpython.Path",), [py_info.system_executable])
    sources = list(RustPythonPosix.sources(interpreter=py_info))
    assert len(sources) == 1
    assert contains_exe(sources, py_info.system_executable)


@pytest.mark.parametrize("py_info_name", ["rustpython_windows"])
def test_sources_windows(py_info: MagicMock, mock_files: object) -> None:
    mock_files(("virtualenv.create.via_global_ref.builtin.rustpython.Path",), [py_info.system_executable])
    sources = list(RustPythonWindows.sources(interpreter=py_info))
    assert len(sources) == 1
    assert contains_exe(sources, py_info.system_executable)


def test_exe_names() -> None:
    interpreter = MagicMock()
    interpreter.version_info = MagicMock(major=3, minor=14)
    names = RustPythonPosix.exe_names(interpreter)
    assert names == {"rustpython", "python", "python3", "python3.14"}
