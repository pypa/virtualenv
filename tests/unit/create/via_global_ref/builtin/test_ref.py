from __future__ import annotations

import os
import shutil
import subprocess
import sys
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
    # Mock the source so the mode is ours to pick - Windows only sets execute bits for .exe/.bat/.cmd/.com.
    src = mocker.create_autospec(Path, instance=True)
    src.stat.return_value = mocker.create_autospec(os.stat_result, instance=True, st_mode=request.param)
    return ExePathRefToDest(src, targets=["python"], dest=mocker.create_autospec(Path, instance=True))


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


@pytest.mark.skipif(os.name != "posix", reason="POSIX permission bits")
@pytest.mark.parametrize(
    ("mask", "expected"),
    [
        pytest.param(0o022, 0o755, id="normal"),
        pytest.param(0o027, 0o750, id="no-other"),
        pytest.param(0o077, 0o700, id="private"),
        pytest.param(0o011, 0o744, id="read-without-execute"),
        pytest.param(
            0o177,
            0o700,
            marks=pytest.mark.skipif(
                sys.platform != "linux" or not hasattr(os, "getxattr"), reason="Linux default ACL detection"
            ),
            id="owner-execute-masked",
        ),
    ],
)
@pytest.mark.parametrize("source_mode", [0o755, 0o644])
def test_copied_executables_keep_umask(tmp_path: Path, mask: int, expected: int, source_mode: int) -> None:
    source = tmp_path / "source"
    source.write_bytes(b"interpreter")
    source.chmod(source_mode)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    ref = ExePathRefToDest(source, targets=["python", "python3"], dest=lambda _creator, _src: bin_dir / "python")
    previous = os.umask(mask)
    try:
        ref.run(object(), symlinks=False)
    finally:
        os.umask(previous)
    assert [(bin_dir / name).stat().st_mode & 0o777 for name in ("python", "python3")] == [expected, expected]


@pytest.mark.skipif(os.name != "posix" or shutil.which("setfacl") is None, reason="requires POSIX default ACL")
@pytest.mark.parametrize(("group", "expected"), [("rwx", 0o750), ("r--", 0o740)])
def test_copied_executables_inherit_default_acl(tmp_path: Path, group: str, expected: int) -> None:
    source = tmp_path / "source"
    source.write_bytes(b"interpreter")
    source.chmod(0o755)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    bin_dir.chmod(0o775)
    subprocess.run(["setfacl", "-d", "-m", f"u::rwx,g::{group},o::---", str(bin_dir)], check=True)
    ref = ExePathRefToDest(source, targets=["python", "python3"], dest=lambda _creator, _src: bin_dir / "python")
    previous = os.umask(0o077)
    try:
        ref.run(object(), symlinks=False)
    finally:
        os.umask(previous)

    assert (
        bin_dir.stat().st_mode & 0o777,
        [(bin_dir / name).stat().st_mode & 0o777 for name in ("python", "python3")],
    ) == (
        0o775,
        [expected, expected],
    )


@pytest.mark.skipif(os.name != "posix" or shutil.which("setfacl") is None, reason="requires POSIX default ACL")
def test_copied_interpreter_needs_owner_execute_in_default_acl(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.write_bytes(b"interpreter")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    subprocess.run(["setfacl", "-d", "-m", "u::rw-,g::r-x,o::---", str(bin_dir)], check=True)
    ref = ExePathRefToDest(source, targets=["python"], dest=lambda _creator, _src: bin_dir / "python")
    with pytest.raises(PermissionError, match=r"owner-executable.*--symlinks"):
        ref.run(object(), symlinks=False)


@pytest.fixture
def creator_meta(mocker: MockerFixture) -> Callable[[PathRef], BuiltinViaGlobalRefMeta]:
    # Force symlink support on, otherwise a host without it starts with symlink_error already set.
    mocker.patch.object(api, "fs_supports_symlink", return_value=True, autospec=True)

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


def absent_ref(tmp_path: Path, when: RefWhen) -> PathRefToDest:
    return PathRefToDest(tmp_path / "absent", dest=lambda _creator, src: src, when=when)


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
    assert creator_meta(ref).sources == [ref] * collected
