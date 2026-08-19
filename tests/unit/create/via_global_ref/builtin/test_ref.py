from __future__ import annotations

import os
from stat import S_IXGRP, S_IXOTH, S_IXUSR

import pytest

from virtualenv.create.via_global_ref.builtin.ref import ExePathRef


class FakeSrc:
    """Stands in for the source path, so the permission bits work the same on Windows and POSIX."""

    def __init__(self, mode):
        self.mode = mode
        self.stat_calls = 0

    def exists(self):
        return True

    def stat(self):
        self.stat_calls += 1
        return os.stat_result((self.mode, 0, 0, 0, 0, 0, 0, 0, 0, 0))


class Ref(ExePathRef):
    def run(self, creator, symlinks):
        raise NotImplementedError


@pytest.mark.parametrize("bit", [S_IXUSR, S_IXGRP, S_IXOTH])
def test_can_run_with_execute_bit(bit) -> None:
    assert Ref(FakeSrc(0o644 | bit)).can_run is True


def test_can_run_without_execute_bit() -> None:
    assert Ref(FakeSrc(0o644)).can_run is False


def test_can_run_is_cached() -> None:
    src = FakeSrc(0o644)
    ref = Ref(src)
    assert ref.can_run is False
    assert ref.can_run is False
    assert src.stat_calls == 1
