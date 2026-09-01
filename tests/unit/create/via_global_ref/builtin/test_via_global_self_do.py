from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from virtualenv.create.via_global_ref.builtin.ref import PathRefToDest, RefWhen
from virtualenv.create.via_global_ref.builtin.via_global_self_do import (
    BuiltinViaGlobalRefMeta,
    ViaGlobalRefVirtualenvBuiltin,
)

if TYPE_CHECKING:
    from collections.abc import Generator
    from pathlib import Path


def apply_sources(refs: list[PathRefToDest]) -> BuiltinViaGlobalRefMeta:
    class Creator(ViaGlobalRefVirtualenvBuiltin):
        @classmethod
        def sources(cls, interpreter: object) -> Generator[PathRefToDest]:  # ruff:ignore[unused-class-method-argument]
            yield from refs

    meta = BuiltinViaGlobalRefMeta()
    Creator._sources_can_be_applied(None, meta)  # ruff:ignore[private-member-access]
    return meta


def missing_ref(tmp_path: Path, when: RefWhen) -> PathRefToDest:
    return PathRefToDest(tmp_path / "does-not-exist", dest=lambda _creator, src: src, when=when)


def test_missing_any_source_disables_the_creator(tmp_path: Path) -> None:
    meta = apply_sources([missing_ref(tmp_path, RefWhen.ANY)])
    assert meta.error is not None
    assert "missing required file" in meta.error
    assert not meta.sources  # the phantom source must not reach create()


def test_missing_copy_source_disables_only_copying(tmp_path: Path) -> None:
    meta = apply_sources([missing_ref(tmp_path, RefWhen.COPY)])
    assert meta.copy_error is not None
    assert "missing required file" in meta.copy_error


def test_missing_symlink_source_disables_only_symlinking(tmp_path: Path) -> None:
    meta = apply_sources([missing_ref(tmp_path, RefWhen.SYMLINK)])
    assert meta.symlink_error is not None
    assert "missing required file" in meta.symlink_error


@pytest.mark.parametrize("when", [RefWhen.ANY, RefWhen.COPY, RefWhen.SYMLINK])
def test_existing_source_is_collected(tmp_path: Path, when: RefWhen) -> None:
    present = tmp_path / "present"
    present.write_text("")
    meta = apply_sources([PathRefToDest(present, dest=lambda _creator, src: src, when=when)])
    assert meta.error is None
    assert len(meta.sources) == 1
