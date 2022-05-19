from functools import partial

from virtualenv.create.via_global_ref.builtin.ref import ExePathRefToDest, PathRefToDest

__all__ = (
    "assert_contains_ref",
    "assert_contains_exe",
)


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
