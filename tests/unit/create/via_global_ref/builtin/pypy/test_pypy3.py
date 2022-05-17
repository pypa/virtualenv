from __future__ import absolute_import, unicode_literals

from functools import partial

import pytest

from tests.unit.create.via_global_ref.builtin.path_mock import path_mock
from virtualenv.create.via_global_ref.builtin.pypy.pypy3 import PyPy3Posix
from virtualenv.create.via_global_ref.builtin.ref import ExePathRefToDest, PathRefToDest
from virtualenv.util.path import Path


def fake_paths(mocker, paths):
    PathMock = path_mock(paths)
    for path in (
        "virtualenv.create.via_global_ref.builtin.pypy.common.Path",
        "virtualenv.create.via_global_ref.builtin.pypy.pypy3.Path",
    ):
        mocker.patch(path, PathMock)


def fake_libs(mocker, paths):
    libs = tuple(map(Path, paths))
    mocker.patch.object(PyPy3Posix, "_shared_libs", return_value=libs)


def is_ref(ref):
    return isinstance(ref, PathRefToDest)


def is_ref_exe(ref):
    return isinstance(ref, ExePathRefToDest)


def has_src(src, ref):
    return ref.src.as_posix() == src


def assert_contains_exe(sources, src):
    """Assert that the one and only executeable in sources is src"""
    exes = tuple(filter(is_ref_exe, sources))
    assert len(exes) == 1
    exe = exes[0]
    assert has_src(src, exe)


def assert_contains_ref(sources, src):
    """Assert that src appears in sources"""
    refs = filter(is_ref, sources)
    has_given_src = partial(has_src, src)
    refs_to_given_src = filter(has_given_src, refs)
    assert any(refs_to_given_src)


@pytest.mark.parametrize("py_info_name", ["portable_pypy38"])
def test_portable_pypy3_virtualenvs_get_their_libs(mocker, py_info):
    fake_paths(
        mocker,
        [
            "/tmp/pypy3.8-v7.3.8-linux64/bin/pypy",
            "/tmp/pypy3.8-v7.3.8-linux64/lib/libgdbm.so.4",
        ],
    )
    fake_libs(
        mocker,
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
def test_debian_pypy37_virtualenvs(mocker, py_info):
    # Debian's pypy3 layout, installed to /usr, before 3.8 allowed a /usr prefix
    fake_paths(
        mocker,
        [
            "/usr/bin/pypy3",
        ],
    )
    fake_libs(
        mocker,
        [
            "/usr/lib/pypy3/bin/libpypy3-c.so",
        ],
    )

    sources = tuple(PyPy3Posix.sources(interpreter=py_info))
    assert_contains_exe(sources, "/usr/bin/pypy3")
    assert_contains_ref(sources, "/usr/lib/pypy3/bin/libpypy3-c.so")
    assert len(sources) == 2


@pytest.mark.parametrize("py_info_name", ["deb_pypy38"])
def test_debian_pypy38_virtualenvs_exclude_usr(mocker, py_info):
    fake_paths(
        mocker,
        [
            "/usr/bin/pypy3",
            "/usr/lib/foo",
        ],
    )
    # libpypy3-c.so lives on the ld search path
    fake_libs(mocker, [])

    sources = tuple(PyPy3Posix.sources(interpreter=py_info))
    assert_contains_exe(sources, "/usr/bin/pypy3")
    assert len(sources) == 1
