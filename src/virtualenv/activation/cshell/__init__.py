from __future__ import annotations

import shlex
from typing import TYPE_CHECKING

from virtualenv.activation.via_template import ViaTemplateActivator

if TYPE_CHECKING:
    from collections.abc import Iterator

    from python_discovery import PythonInfo


class CShellActivator(ViaTemplateActivator):
    @classmethod
    def supports(cls, interpreter: PythonInfo) -> bool:
        return interpreter.os != "nt"

    def templates(self) -> Iterator[str]:
        yield "activate.csh"

    @staticmethod
    def quote(string: str) -> str:
        # csh runs history substitution before it parses quotes, so a ! survives shlex.quote's single
        # quotes and aborts the whole script with "Event not found"; only a backslash suppresses it
        return shlex.quote(string).replace("!", "\\!")


__all__ = [
    "CShellActivator",
]
