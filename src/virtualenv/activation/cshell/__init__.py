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
        # csh expands history inside single quotes and parses unquoted percent signs as expression operators.
        quoted: Final = shlex.quote(string)
        return (f"'{quoted}'" if quoted == string else quoted).replace("!", "'\\!'")

    def substitutions(self, replacements: dict[str, str], creator: Creator) -> dict[str, str]:
        # carries its own quoting, so it cannot go through the shared quote() pass with the other replacements;
        # tcsh and plain csh disagree on whether % needs escaping, so activate.csh picks one of these at runtime
        display = creator.env_name if self.flag_prompt is None else self.flag_prompt
        return {
            **super().substitutions(replacements, creator),
            _PROMPT_DISPLAY_TCSH: _prompt_literal(display, tcsh=True),
            _PROMPT_DISPLAY_PLAIN: _prompt_literal(display, tcsh=False),
        }


def _prompt_literal(value: str, *, tcsh: bool) -> str:
    """Prompt drawing interprets history escapes and tcsh percent codes a second time."""
    parts = ["'"]
    for char in value:
        if char == "'":
            parts.append("'\"'\"'")
        elif char == "!":
            parts.append("'\\\\'\\!")
        elif char == "%" and tcsh:
            parts.append("%%")
        elif char == "^" and tcsh:
            parts.append("'\\\\^'")
        elif char == "\\":
            parts.append("'\\\\\\\\'")
        else:
            parts.append(char)
    parts.append("'")
    return "".join(parts)


__all__ = [
    "CShellActivator",
]
