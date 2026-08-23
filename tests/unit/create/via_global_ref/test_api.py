from __future__ import annotations

import os
from stat import S_IXGRP, S_IXOTH, S_IXUSR

import pytest

from virtualenv.create.via_global_ref import api
from virtualenv.create.via_global_ref.builtin.ref import ExePathRefToDest


def test_can_symlink_when_symlinks_not_enabled(mocker) -> None:
    mocker.patch.object(api, "fs_supports_symlink", return_value=False)
    assert api.ViaGlobalRefMeta().can_symlink is False


def _exe_ref(mocker, mode: int) -> ExePathRefToDest:
    """Build a ref whose source reports mode, so the permission bits behave the same on Windows and POSIX."""
    src = mocker.Mock()
    src.exists.return_value = True
    src.stat.return_value = os.stat_result((mode, 0, 0, 0, 0, 0, 0, 0, 0, 0))
    return ExePathRefToDest(src, targets=["python"], dest=mocker.Mock())


@pytest.mark.parametrize("bit", [S_IXUSR, S_IXGRP, S_IXOTH])
def test_can_run_with_execute_bit(mocker, bit) -> None:
    assert _exe_ref(mocker, 0o644 | bit).can_run is True


def test_can_run_without_execute_bit(mocker) -> None:
    assert _exe_ref(mocker, 0o644).can_run is False


def test_can_run_is_cached(mocker) -> None:
    ref = _exe_ref(mocker, 0o644)
    assert ref.can_run is False
    assert ref.can_run is False
    assert ref.src.stat.call_count == 1
