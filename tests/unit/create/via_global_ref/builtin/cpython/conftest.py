from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from virtualenv.create.via_global_ref.builtin.cpython.cpython3 import CPython3Posix

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from pytest_mock import MockerFixture

    from tests.types import MakeInterpreter
    from virtualenv.create.via_global_ref.builtin.ref import PathRefToDest

    CollectSources = Callable[[dict[str, object]], list[PathRefToDest]]


@pytest.fixture
def collect_sources(tmp_path: Path, make_interpreter: MakeInterpreter, mocker: MockerFixture) -> CollectSources:
    def _collect(sysconfig_vars: dict[str, object]) -> list[PathRefToDest]:
        interpreter = make_interpreter(
            sysconfig_vars={**sysconfig_vars, "PYTHONFRAMEWORK": ""},
            prefix=str(tmp_path),
        )
        interpreter.system_executable = str(tmp_path / "bin" / "python3")
        mocker.patch(
            "virtualenv.create.via_global_ref.builtin.cpython.cpython3.Path.exists",
            return_value=True,
        )
        return list(CPython3Posix.sources(interpreter))

    return _collect
