from __future__ import annotations

from typing import Protocol


class _VersionInfo(Protocol):
    major: int
    minor: int


class Interpreter(Protocol):
    prefix: str
    system_prefix: str
    system_executable: str
    free_threaded: bool
    version_info: _VersionInfo
    sysconfig_vars: dict[str, object]


class MakeInterpreter(Protocol):
    def __call__(
        self,
        sysconfig_vars: dict[str, object] | None = ...,
        prefix: str = ...,
        free_threaded: bool = ...,
        version_info: tuple[int, ...] = ...,
    ) -> Interpreter: ...
