from __future__ import annotations

from pathlib import Path
from stat import S_IXGRP, S_IXOTH, S_IXUSR
from typing import TYPE_CHECKING

import pytest

from virtualenv.create.via_global_ref.builtin.ref import ExePathRefToDest

if TYPE_CHECKING:
    from pytest_mock import MockerFixture


@pytest.fixture
def exe_ref(mocker: MockerFixture, request: pytest.FixtureRequest) -> ExePathRefToDest:
    """Mock the source so the mode is ours to pick - Windows only sets execute bits for .exe/.bat/.cmd/.com."""
    src = mocker.create_autospec(Path, instance=True)
    src.stat.return_value = mocker.MagicMock(st_mode=request.param)  # create_autospec drops dotted kwargs before 3.12
    return ExePathRefToDest(src, targets=["python"], dest=mocker.Mock())


@pytest.mark.parametrize(
    ("exe_ref", "expected"),
    [
        pytest.param(0o644 | S_IXUSR, True, id="user"),
        pytest.param(0o644 | S_IXGRP, True, id="group"),
        pytest.param(0o644 | S_IXOTH, True, id="other"),
        pytest.param(0o644, False, id="none"),
    ],
    indirect=["exe_ref"],
)
def test_can_run_honours_every_execute_bit(exe_ref: ExePathRefToDest, expected: bool) -> None:
    assert exe_ref.can_run is expected


@pytest.mark.parametrize("exe_ref", [pytest.param(0o644, id="none")], indirect=True)
def test_can_run_is_cached(exe_ref: ExePathRefToDest) -> None:
    assert exe_ref.can_run is False
    assert exe_ref.can_run is False
    assert exe_ref.src.stat.call_count == 1
