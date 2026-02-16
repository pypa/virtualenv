from __future__ import annotations

from typing import TYPE_CHECKING

from virtualenv.create.via_global_ref.builtin.cpython.cpython3 import CPython3Posix
from virtualenv.create.via_global_ref.builtin.ref import PathRefToDest, RefWhen

if TYPE_CHECKING:
    from pathlib import Path

    from conftest import CollectSources

    from tests.types import MakeInterpreter


def _shared_lib_copy_refs(sources: list[PathRefToDest]) -> list[PathRefToDest]:
    return [s for s in sources if isinstance(s, PathRefToDest) and s.when == RefWhen.COPY]


def test_shared_lib_included(tmp_path: Path, collect_sources: CollectSources) -> None:
    lib_dir = tmp_path / "lib"
    lib_dir.mkdir()
    (lib_dir / "libpython3.14.so").touch()
    sources = collect_sources({"Py_ENABLE_SHARED": 1, "INSTSONAME": "libpython3.14.so", "LIBDIR": str(lib_dir)})
    shared_refs = _shared_lib_copy_refs(sources)
    assert len(shared_refs) == 1
    assert shared_refs[0].src.name == "libpython3.14.so"


def test_shared_lib_excluded_when_static(collect_sources: CollectSources) -> None:
    sources = collect_sources({"Py_ENABLE_SHARED": 0})
    assert _shared_lib_copy_refs(sources) == []


def test_shared_lib_excluded_when_no_lib_name(collect_sources: CollectSources) -> None:
    sources = collect_sources({"Py_ENABLE_SHARED": 1})
    assert _shared_lib_copy_refs(sources) == []


def test_shared_lib_excluded_when_no_lib_dir(collect_sources: CollectSources) -> None:
    sources = collect_sources({"Py_ENABLE_SHARED": 1, "INSTSONAME": "libpython3.14.so"})
    assert _shared_lib_copy_refs(sources) == []


def test_shared_lib_excluded_when_file_missing(tmp_path: Path, make_interpreter: MakeInterpreter) -> None:
    lib_dir = tmp_path / "lib"
    lib_dir.mkdir()
    interpreter = make_interpreter(
        sysconfig_vars={
            "Py_ENABLE_SHARED": 1,
            "INSTSONAME": "libpython3.14.so",
            "LIBDIR": str(lib_dir),
            "PYTHONFRAMEWORK": "",
        },
        prefix=str(tmp_path),
    )
    interpreter.system_executable = str(tmp_path / "bin" / "python3")
    sources = list(CPython3Posix.sources(interpreter))
    assert _shared_lib_copy_refs(sources) == []
