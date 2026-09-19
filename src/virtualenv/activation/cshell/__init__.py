from __future__ import annotations

import shlex
from typing import TYPE_CHECKING, Final

from virtualenv.activation.via_template import ViaTemplateActivator

if TYPE_CHECKING:
    from collections.abc import Iterator

    from python_discovery import PythonInfo

    from virtualenv.create.creator import Creator

_PROMPT_DISPLAY_TCSH: Final[str] = "__VIRTUAL_PROMPT_DISPLAY_TCSH__"
_PROMPT_DISPLAY_PLAIN: Final[str] = "__VIRTUAL_PROMPT_DISPLAY_PLAIN__"


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
        # carries its own quoting, so it cannot go through the shared quote() pass with the other replacements;
        # tcsh and plain csh disagree on whether % needs escaping, so activate.csh picks one of these at runtime
        display = creator.env_name if self.flag_prompt is None else self.flag_prompt
        text = text.replace(_PROMPT_DISPLAY_TCSH, _prompt_literal(display, tcsh=True))
        return text.replace(_PROMPT_DISPLAY_PLAIN, _prompt_literal(display, tcsh=False))


def _prompt_literal(value: str, *, tcsh: bool) -> str:
    r"""Build csh source whose ``prompt`` renders ``value`` unchanged.

    Both csh and tcsh expand the prompt every time it draws it, and a literal ``!`` turns into the history event number
    in either; only ``\!`` survives that pass, and it has to reach the variable as a real backslash, which costs a
    second one in the source. ``%`` is different: tcsh treats a bare ``%`` as the start of an escape such as ``%p`` for
    the time, and only a doubled ``%%`` survives as a literal percent, but plain csh has no such escape at all - a bare
    ``%`` is already literal there, and doubling it would show two. Confirmed on tcsh 6.24 and on Debian's bsd-csh
    package, which is what "csh" actually resolves to on Debian and Ubuntu.

    """
    parts = ["'"]
    for char in value:
        if char == "'":
            parts.append("'\\''")
        elif char == "!":
            parts.append("\\\\!")
        elif char == "%" and tcsh:
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
