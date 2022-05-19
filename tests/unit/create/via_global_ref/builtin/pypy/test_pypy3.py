from __future__ import absolute_import, unicode_literals

import sys

import pytest
from testing.assertions import assert_contains_exe, assert_contains_ref

from virtualenv.create.via_global_ref.builtin.pypy.pypy3 import PyPy3Posix

# `mock_files()` in these paths.
PYPY3_PATHS = (
    "virtualenv.create.via_global_ref.builtin.pypy.common.Path",
    "virtualenv.create.via_global_ref.builtin.pypy.pypy3.Path",
)


@pytest.mark.skipif(sys.platform == "win32", reason="host_lib paths are POSIX")
@pytest.mark.parametrize("py_info_name", ["portable_pypy38"])
@pytest.mark.parametrize("mock_paths", [PYPY3_PATHS])
def test_portable_pypy3_virtualenvs_get_their_libs(py_info, mock_files, mock_pypy_libs):
    mock_files(
        [
            "/tmp/pypy3.8-v7.3.8-linux64/bin/pypy",
            "/tmp/pypy3.8-v7.3.8-linux64/lib/libgdbm.so.4",
        ],
    )
    mock_pypy_libs(
        PyPy3Posix,
        [
            "/tmp/pypy3.8-v7.3.8-linux64/bin/libpypy3-c.so",
        ],
    )

    sources = tuple(PyPy3Posix.sources(interpreter=py_info))

    assert_contains_exe(sources, "/tmp/pypy3.8-v7.3.8-linux64/bin/pypy")
    assert len(sources) > 2
    assert_contains_ref(sources, "/tmp/pypy3.8-v7.3.8-linux64/bin/libpypy3-c.so")
    assert_contains_ref(sources, "/tmp/pypy3.8-v7.3.8-linux64/lib/libgdbm.so.4")


@pytest.mark.parametrize("py_info_name", ["deb_pypy37"])
@pytest.mark.parametrize("mock_paths", [PYPY3_PATHS])
def test_debian_pypy37_virtualenvs(py_info, mock_files, mock_pypy_libs):
    # Debian's pypy3 layout, installed to /usr, before 3.8 allowed a /usr prefix
    mock_files(["/usr/bin/pypy3"])
    mock_pypy_libs(PyPy3Posix, ["/usr/lib/pypy3/bin/libpypy3-c.so"])

    sources = tuple(PyPy3Posix.sources(interpreter=py_info))

    assert_contains_exe(sources, "/usr/bin/pypy3")
    assert_contains_ref(sources, "/usr/lib/pypy3/bin/libpypy3-c.so")
    assert len(sources) == 2


@pytest.mark.parametrize("py_info_name", ["deb_pypy38"])
@pytest.mark.parametrize("mock_paths", [PYPY3_PATHS])
def test_debian_pypy38_virtualenvs_exclude_usr(py_info, mock_files, mock_pypy_libs):
    mock_files(["/usr/bin/pypy3", "/usr/lib/foo"])
    # libpypy3-c.so lives on the ld search path
    mock_pypy_libs(PyPy3Posix, [])

    sources = tuple(PyPy3Posix.sources(interpreter=py_info))

    assert_contains_exe(sources, "/usr/bin/pypy3")
    assert len(sources) == 1
