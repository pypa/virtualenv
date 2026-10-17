from __future__ import annotations

import logging
import shlex
from typing import TYPE_CHECKING, Final

from virtualenv.activation.via_template import ViaTemplateActivator
from virtualenv.util.text import collapse_line_boundaries

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

    from python_discovery import PythonInfo

    from virtualenv.create.creator import Creator

_LOGGER: Final = logging.getLogger(__name__)
_PROMPT_DISPLAY_TCSH: Final[str] = "__VIRTUAL_PROMPT_DISPLAY_TCSH__"
_PROMPT_DISPLAY_PLAIN: Final[str] = "__VIRTUAL_PROMPT_DISPLAY_PLAIN__"


class CShellActivator(ViaTemplateActivator):
    @classmethod
    def supports(cls, interpreter: PythonInfo) -> bool:
        return interpreter.os != "nt"

    def templates(self) -> Iterator[str]:
        yield "activate.csh"
        yield "deactivate.csh"

    def generate(self, creator: Creator) -> list[Path]:
        values: Final = super().replacements(creator, creator.bin_dir)
        if any("\n" in values[key] for key in ("__VIRTUAL_ENV__", "__TCL_LIBRARY__", "__TK_LIBRARY__")):
            _LOGGER.warning("skipping csh activation scripts: a filesystem path contains a newline")
            for template in self.templates():
                (creator.bin_dir / self.as_name(template)).unlink(missing_ok=True)
            return []
        return super().generate(creator)

    @staticmethod
    def quote(string: str) -> str:
        # csh expands history inside single quotes and parses unquoted percent signs as expression operators.
        # Backslashes outside quotes retain their meaning with tcsh's backslash_quote option.
        quoted: Final = shlex.quote(string)
        return (f"'{quoted}'" if quoted == string else quoted).replace("\\", "'\\\\'").replace("!", "'\\!'")

    def substitutions(self, replacements: dict[str, str], creator: Creator) -> dict[str, str]:
        # Normalize display text without changing the filesystem paths used by activation.
        values: Final = {
            **replacements,
            "__VIRTUAL_PROMPT__": collapse_line_boundaries(replacements["__VIRTUAL_PROMPT__"]),
        }
        display: Final = collapse_line_boundaries(creator.env_name if self.flag_prompt is None else self.flag_prompt)
        return {
            **super().substitutions(values, creator),
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
            parts.append("'\\\\\\\\'" if tcsh else "'\\\\'")
        else:
            parts.append(char)
    parts.append("'")
    return "".join(parts)


__all__ = [
    "CShellActivator",
]
