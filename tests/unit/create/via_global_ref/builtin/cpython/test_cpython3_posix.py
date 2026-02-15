from __future__ import annotations

from typing import TYPE_CHECKING

from virtualenv.create.via_global_ref.builtin.cpython.cpython3 import CPython3Posix
from virtualenv.create.via_global_ref.builtin.ref import PathRefToDest, RefWhen

if TYPE_CHECKING:
    from pathlib import Path

    from conftest import MakeInterpreter
    from pytest_mock import MockerFixture


def test_shared_libpython_returned_when_shared(tmp_path: Path, make_interpreter: MakeInterpreter) -> None:
    lib_dir = tmp_path / "lib"
    lib_dir.mkdir()
    lib_file = lib_dir / "libpython3.14.so"
    lib_file.touch()
    interpreter = make_interpreter(
        sysconfig_vars={"Py_ENABLE_SHARED": 1, "INSTSONAME": "libpython3.14.so", "LIBDIR": str(lib_dir)},
    )
    result = CPython3Posix._shared_libpython(interpreter)  # noqa: SLF001
    assert result == lib_file


def test_shared_libpython_none_when_not_shared(make_interpreter: MakeInterpreter) -> None:
    interpreter = make_interpreter(sysconfig_vars={"Py_ENABLE_SHARED": 0})
    assert CPython3Posix._shared_libpython(interpreter) is None  # noqa: SLF001


def test_shared_libpython_none_when_no_instsoname(make_interpreter: MakeInterpreter) -> None:
    interpreter = make_interpreter(sysconfig_vars={"Py_ENABLE_SHARED": 1})
    assert CPython3Posix._shared_libpython(interpreter) is None  # noqa: SLF001


def test_shared_libpython_none_when_no_libdir(make_interpreter: MakeInterpreter) -> None:
    interpreter = make_interpreter(sysconfig_vars={"Py_ENABLE_SHARED": 1, "INSTSONAME": "libpython3.14.so"})
    assert CPython3Posix._shared_libpython(interpreter) is None  # noqa: SLF001


def test_shared_libpython_none_when_lib_missing(tmp_path: Path, make_interpreter: MakeInterpreter) -> None:
    interpreter = make_interpreter(
        sysconfig_vars={"Py_ENABLE_SHARED": 1, "INSTSONAME": "libpython3.14.so", "LIBDIR": str(tmp_path)},
    )
    assert CPython3Posix._shared_libpython(interpreter) is None  # noqa: SLF001


def test_sources_includes_shared_lib_with_copy_when(
    tmp_path: Path, mocker: MockerFixture, make_interpreter: MakeInterpreter
) -> None:
    lib_dir = tmp_path / "lib"
    lib_dir.mkdir()
    (lib_dir / "libpython3.14.so").touch()
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
    mocker.patch(
        "virtualenv.create.via_global_ref.builtin.cpython.cpython3.Path.exists",
        return_value=True,
    )
    sources = list(CPython3Posix.sources(interpreter))
    shared_refs = [s for s in sources if isinstance(s, PathRefToDest) and s.when == RefWhen.COPY]
    assert len(shared_refs) == 1
    assert shared_refs[0].src.name == "libpython3.14.so"
