from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from testing.helpers import contains_exe, contains_ref
from testing.path import join as path

from virtualenv.create.via_global_ref.builtin.pypy.pypy3 import PyPy3Posix
from virtualenv.create.via_global_ref.builtin.ref import PathRefToDest

if TYPE_CHECKING:
    from pathlib import Path

    from pytest_mock import MockerFixture

PYPY3_PATH = (
    "virtualenv.create.via_global_ref.builtin.pypy.common.Path",
    "virtualenv.create.via_global_ref.builtin.pypy.pypy3.Path",
)


# In `PyPy3Posix.sources()` `host_lib` will be broken in Python 2 for Windows,
# so `py_file` will not be in sources.
@pytest.mark.parametrize("py_info_name", ["portable_pypy38"])
def test_portable_pypy3_virtualenvs_get_their_libs(py_info, mock_files, mock_pypy_libs):
    py_file = path(py_info.prefix, "lib/libgdbm.so.4")
    mock_files(PYPY3_PATH, [py_info.system_executable, py_file])
    lib_file = path(py_info.prefix, "bin/libpypy3-c.so")
    mock_pypy_libs(PyPy3Posix, [lib_file])
    sources = tuple(PyPy3Posix.sources(interpreter=py_info))
    assert len(sources) > 2
    assert contains_exe(sources, py_info.system_executable)
    assert contains_ref(sources, py_file)
    assert contains_ref(sources, lib_file)


@pytest.mark.parametrize("py_info_name", ["deb_pypy37"])
def test_debian_pypy37_virtualenvs(py_info, mock_files, mock_pypy_libs):
    # Debian's pypy3 layout, installed to /usr, before 3.8 allowed a /usr prefix
    mock_files(PYPY3_PATH, [py_info.system_executable])
    lib_file = path(py_info.prefix, "bin/libpypy3-c.so")
    mock_pypy_libs(PyPy3Posix, [lib_file])
    sources = tuple(PyPy3Posix.sources(interpreter=py_info))
    assert len(sources) == 2
    assert contains_exe(sources, py_info.system_executable)
    assert contains_ref(sources, lib_file)


@pytest.mark.parametrize("py_info_name", ["deb_pypy38"])
def test_debian_pypy38_virtualenvs_exclude_usr(py_info, mock_files, mock_pypy_libs):
    mock_files(PYPY3_PATH, [py_info.system_executable, "/usr/lib/foo"])
    # libpypy3-c.so lives on the ld search path
    mock_pypy_libs(PyPy3Posix, [])
    sources = tuple(PyPy3Posix.sources(interpreter=py_info))
    assert len(sources) == 1
    assert contains_exe(sources, py_info.system_executable)


def test_pypy_portable_deps_txt(tmp_path: Path, mocker: MockerFixture) -> None:
    host_lib = tmp_path / "lib"
    host_lib.mkdir()
    stdlib = host_lib / "pypy3.10"
    stdlib.mkdir()
    (host_lib / "libssl.so").touch()
    (host_lib / "libcrypto.so").touch()
    (host_lib / "unneeded.so").touch()
    deps_file = host_lib / "PYPY_PORTABLE_DEPS.txt"
    deps_file.write_text("libssl.so\nlibcrypto.so\n", encoding="utf-8")

    interpreter = MagicMock()
    interpreter.system_prefix = str(tmp_path)
    interpreter.system_executable = str(tmp_path / "bin" / "pypy3")
    interpreter.system_stdlib = str(stdlib)
    interpreter.version_info = MagicMock(major=3, minor=10)

    mocker.patch.object(PyPy3Posix, "_shared_libs", return_value=[])

    sources = list(PyPy3Posix.sources(interpreter))
    ref_names = {s.src.name for s in sources if isinstance(s, PathRefToDest)}
    assert "libssl.so" in ref_names
    assert "libcrypto.so" in ref_names
    assert "unneeded.so" not in ref_names
