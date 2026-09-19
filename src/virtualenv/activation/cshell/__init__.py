from __future__ import annotations

import shlex
from typing import TYPE_CHECKING, Final

from virtualenv.activation.via_template import ViaTemplateActivator

if TYPE_CHECKING:
    from collections.abc import Iterator

    from python_discovery import PythonInfo

    from virtualenv.create.creator import Creator

_PROMPT_DISPLAY: Final[str] = "__VIRTUAL_PROMPT_DISPLAY__"


class CShellActivator(ViaTemplateActivator):
    @classmethod
    def supports(cls, interpreter: PythonInfo) -> bool:
        return interpreter.os != "nt"

    def templates(self) -> Iterator[str]:
        yield "activate.csh"
        yield "deactivate.csh"

    @staticmethod
    def quote(string: str) -> str:
        # csh runs history substitution before it parses quotes, so a ! survives shlex.quote's single
        # quotes and aborts the whole script with "Event not found"; only a backslash suppresses it
        return shlex.quote(string).replace("!", "\\!")

    def instantiate_template(self, replacements: dict[str, str], template: str, creator: Creator) -> str:
        text = super().instantiate_template(replacements, template, creator)
        # carries its own quoting, so it cannot go through the shared quote() pass with the other replacements
        display = creator.env_name if self.flag_prompt is None else self.flag_prompt
        return text.replace(_PROMPT_DISPLAY, _prompt_literal(display))


def _prompt_literal(value: str) -> str:
    r"""Build csh source whose ``prompt`` renders ``value`` unchanged.

    csh expands the prompt every time it draws it, so a literal ``!`` turns into the history event number and ``%``
    starts an escape such as ``%p`` for the time. Only ``\!`` and ``%%`` survive that pass, and ``\!`` has to reach the
    variable as a real backslash, which costs a second one in the source.

    """
    parts = ["'"]
    for char in value:
        if char == "'":
            parts.append("'\\''")
        elif char == "!":
            parts.append("\\\\!")
        elif char == "%":
            parts.append("%%")
        elif char == "\\":
            parts.append("\\\\")
        else:
            parts.append(char)
    parts.append("'")
    return "".join(parts)


__all__ = [
    "CShellActivator",
]
