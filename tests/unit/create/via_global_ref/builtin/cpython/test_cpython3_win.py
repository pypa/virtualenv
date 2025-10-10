from __future__ import annotations

import pytest
from testing.helpers import contains_exe, contains_ref
from testing.path import join as path

from virtualenv.create.via_global_ref.builtin.cpython.cpython3 import CPython3Windows

CPYTHON3_PATH = (
    "virtualenv.create.via_global_ref.builtin.cpython.common.Path",
    "virtualenv.create.via_global_ref.builtin.cpython.cpython3.Path",
)


@pytest.mark.parametrize("py_info_name", ["cpython3_win_embed"])
def test_2_exe_on_default_py_host(py_info, mock_files):
    mock_files(CPYTHON3_PATH, [py_info.system_executable])
    sources = tuple(CPython3Windows.sources(interpreter=py_info))
    # Default Python exe.
    assert contains_exe(sources, py_info.system_executable)
    # Should always exist.
    assert contains_exe(sources, path(py_info.prefix, "pythonw.exe"))


@pytest.mark.parametrize("py_info_name", ["cpython3_win_embed"])
def test_3_exe_on_not_default_py_host(py_info, mock_files):
    # Not default python host.
    py_info.system_executable = path(py_info.prefix, "python666.exe")
    mock_files(CPYTHON3_PATH, [py_info.system_executable])
    sources = tuple(CPython3Windows.sources(interpreter=py_info))
    # Not default Python exe linked to both the default name and origin.
    assert contains_exe(sources, py_info.system_executable, "python.exe")
    assert contains_exe(sources, py_info.system_executable, "python666.exe")
    # Should always exist.
    assert contains_exe(sources, path(py_info.prefix, "pythonw.exe"))


@pytest.mark.parametrize("py_info_name", ["cpython3_win_embed"])
def test_only_shim(py_info, mock_files):
    shim = path(py_info.system_stdlib, "venv\\scripts\\nt\\python.exe")
    py_files = (
        path(py_info.prefix, "libcrypto-1_1.dll"),
        path(py_info.prefix, "libffi-7.dll"),
        path(py_info.prefix, "_asyncio.pyd"),
        path(py_info.prefix, "_bz2.pyd"),
    )
    mock_files(CPYTHON3_PATH, [shim, *py_files])
    sources = tuple(CPython3Windows.sources(interpreter=py_info))
    assert CPython3Windows.has_shim(interpreter=py_info)
    assert contains_exe(sources, shim)
    assert not contains_exe(sources, py_info.system_executable)
    for file in py_files:
        assert not contains_ref(sources, file)


@pytest.mark.parametrize("py_info_name", ["cpython3_win_embed"])
def test_exe_dll_pyd_without_shim(py_info, mock_files):
    py_files = (
        path(py_info.prefix, "libcrypto-1_1.dll"),
        path(py_info.prefix, "libffi-7.dll"),
        path(py_info.prefix, "_asyncio.pyd"),
        path(py_info.prefix, "_bz2.pyd"),
    )
    mock_files(CPYTHON3_PATH, py_files)
    sources = tuple(CPython3Windows.sources(interpreter=py_info))
    assert not CPython3Windows.has_shim(interpreter=py_info)
    assert contains_exe(sources, py_info.system_executable)
    for file in py_files:
        assert contains_ref(sources, file)


@pytest.mark.parametrize("py_info_name", ["cpython3_win_embed"])
def test_python_zip_if_exists_and_set_in_path(py_info, mock_files):
    python_zip_name = f"python{py_info.version_nodot}.zip"
    python_zip = path(py_info.prefix, python_zip_name)
    mock_files(CPYTHON3_PATH, [python_zip])
    sources = tuple(CPython3Windows.sources(interpreter=py_info))
    assert python_zip in py_info.path
    assert contains_ref(sources, python_zip)


@pytest.mark.parametrize("py_info_name", ["cpython3_win_embed"])
def test_no_python_zip_if_exists_and_not_set_in_path(py_info, mock_files):
    python_zip_name = f"python{py_info.version_nodot}.zip"
    python_zip = path(py_info.prefix, python_zip_name)
    py_info.path.remove(python_zip)
    mock_files(CPYTHON3_PATH, [python_zip])
    sources = tuple(CPython3Windows.sources(interpreter=py_info))
    assert python_zip not in py_info.path
    assert not contains_ref(sources, python_zip)


@pytest.mark.parametrize("py_info_name", ["cpython3_win_embed"])
def test_no_python_zip_if_not_exists(py_info, mock_files):
    python_zip_name = f"python{py_info.version_nodot}.zip"
    python_zip = path(py_info.prefix, python_zip_name)
    # No `python_zip`, just python.exe file.
    mock_files(CPYTHON3_PATH, [py_info.system_executable])
    sources = tuple(CPython3Windows.sources(interpreter=py_info))
    assert python_zip in py_info.path
    assert not contains_ref(sources, python_zip)
