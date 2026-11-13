from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING

import pytest
from python_discovery import PythonInfo
from testing.ref_filters import contains_exe

from virtualenv.create.via_global_ref.builtin.rustpython import RustPython, RustPythonPosix, RustPythonWindows

if TYPE_CHECKING:
    from collections.abc import Callable

    from pytest_mock import MockerFixture


@pytest.mark.parametrize("creator", [RustPython, RustPythonPosix, RustPythonWindows])
def test_class_module(creator: type[RustPython]) -> None:
    assert creator.__module__ == "virtualenv.create.via_global_ref.builtin.rustpython"


@pytest.mark.parametrize("py_info_name", ["rustpython_posix"])
def test_can_describe_rustpython_posix(py_info: PythonInfo) -> None:
    assert RustPythonPosix.can_describe(py_info)


@pytest.mark.parametrize("py_info_name", ["rustpython_windows"])
def test_can_describe_rustpython_windows(py_info: PythonInfo) -> None:
    assert RustPythonWindows.can_describe(py_info)


def test_can_describe_rejects_cpython(mocker: MockerFixture) -> None:
    interpreter = mocker.create_autospec(PythonInfo, instance=True, implementation="CPython", os="posix")
    assert not RustPythonPosix.can_describe(interpreter)
    interpreter.os = "nt"
    assert not RustPythonWindows.can_describe(interpreter)


@pytest.mark.parametrize("py_info_name", ["rustpython_posix"])
def test_sources_posix(py_info: PythonInfo, mock_files: Callable[[tuple[str, ...], list[str | None]], None]) -> None:
    mock_files(("virtualenv.create.via_global_ref.builtin.rustpython.Path",), [py_info.system_executable])
    sources = list(RustPythonPosix.sources(interpreter=py_info))
    assert len(sources) == 1
    assert contains_exe(sources, py_info.system_executable)


@pytest.mark.parametrize("py_info_name", ["rustpython_windows"])
def test_sources_windows(py_info: PythonInfo, mock_files: Callable[[tuple[str, ...], list[str | None]], None]) -> None:
    mock_files(("virtualenv.create.via_global_ref.builtin.rustpython.Path",), [py_info.system_executable])
    sources = list(RustPythonWindows.sources(interpreter=py_info))
    assert len(sources) == 1
    assert contains_exe(sources, py_info.system_executable)


def test_exe_names(mocker: MockerFixture) -> None:
    interpreter = mocker.create_autospec(PythonInfo, instance=True, version_info=SimpleNamespace(major=3, minor=14))
    names = RustPythonPosix.exe_names(interpreter)
    assert names == {"rustpython", "python", "python3", "python3.14"}
