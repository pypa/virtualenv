from __future__ import annotations

from pathlib import Path
from stat import S_IXGRP, S_IXOTH, S_IXUSR
from typing import TYPE_CHECKING

import pytest
from python_discovery import PythonInfo

from virtualenv.create.via_global_ref import api
from virtualenv.create.via_global_ref.builtin.ref import ExePathRefToDest, PathRef, PathRefToDest, RefWhen
from virtualenv.create.via_global_ref.builtin.via_global_self_do import (
    BuiltinViaGlobalRefMeta,
    ViaGlobalRefVirtualenvBuiltin,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Generator

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


@pytest.fixture
def creator_meta(mocker: MockerFixture) -> Callable[[PathRef], BuiltinViaGlobalRefMeta]:
    """Force symlink support on, otherwise a host without it starts with symlink_error already set."""
    mocker.patch.object(api, "fs_supports_symlink", return_value=True)

    def build(ref: PathRef) -> BuiltinViaGlobalRefMeta:
        class Creator(ViaGlobalRefVirtualenvBuiltin):
            @classmethod
            def sources(cls, _interpreter: PythonInfo) -> Generator[PathRef]:
                yield ref

        return Creator.can_create(mocker.create_autospec(PythonInfo, instance=True))

    return build


@pytest.mark.parametrize(
    ("when", "reported_on"),
    [
        pytest.param(RefWhen.ANY, "error", id="any"),
        pytest.param(RefWhen.COPY, "copy_error", id="copy"),
        pytest.param(RefWhen.SYMLINK, "symlink_error", id="symlink"),
    ],
)
def test_missing_source_is_reported_against_its_mode(
    tmp_path: Path, creator_meta: Callable[[PathRef], BuiltinViaGlobalRefMeta], when: RefWhen, reported_on: str
) -> None:
    ref = absent_ref(tmp_path, when)
    assert getattr(creator_meta(ref), reported_on) == f"missing required file {ref}"


@pytest.mark.parametrize(
    ("when", "collected"),
    [
        pytest.param(RefWhen.ANY, False, id="any"),
        pytest.param(RefWhen.COPY, True, id="copy"),
        pytest.param(RefWhen.SYMLINK, True, id="symlink"),
    ],
)
def test_missing_source_reaches_create_unless_both_modes_need_it(
    tmp_path: Path, creator_meta: Callable[[PathRef], BuiltinViaGlobalRefMeta], when: RefWhen, collected: bool
) -> None:
    ref = absent_ref(tmp_path, when)
    assert creator_meta(ref).sources == ([ref] if collected else [])


def absent_ref(tmp_path: Path, when: RefWhen) -> PathRefToDest:
    return PathRefToDest(tmp_path / "absent", dest=lambda _creator, src: src, when=when)
