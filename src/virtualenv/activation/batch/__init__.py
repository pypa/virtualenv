from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING, Final

from virtualenv.activation.via_template import ViaTemplateActivator
from virtualenv.util.text import collapse_line_boundaries

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

    from python_discovery import PythonInfo

    from virtualenv.create.creator import Creator

LOGGER = logging.getLogger(__name__)

# cmd.exe's own command-line parser looks for these regardless of surrounding quotes: confirmed on a
# real Windows runner that `@set "VAR=x & cmd"` still runs `cmd` as a second statement even though the
# whole VAR=value expression is quoted. `(` and `)` are not in this set - confirmed on the same runner
# that `@set "VAR=C:\Program Files (x86)\..."` round-trips unchanged, since parentheses are only special
# to cmd.exe as block delimiters in control-flow syntax (if/for), not as bare characters in a value. `!`
# is only live when the caller already has delayed expansion enabled (`setlocal enabledelayedexpansion`,
# `cmd /V:ON`) - not cmd.exe's default, but confirmed on a real runner that a prompt like `foo!SECRET!`
# then substitutes the actual value of an existing SECRET variable into the prompt, so it is neutered
# unconditionally rather than only when that mode happens to be on.
_CMD_OPERATORS: Final[tuple[str, ...]] = ("&", "|", "<", ">", "^", "!", '"')

# These are valid filename characters that quote() would replace, changing the target directory.
_PATH_UNSAFE_CHARS: Final[tuple[str, ...]] = ("&", "^", "!")

_PATH_REPLACEMENT_NAMES: Final[dict[str, str]] = {
    "__VIRTUAL_ENV__": "the destination directory",
    "__TCL_LIBRARY__": "the interpreter's Tcl library path",
    "__TK_LIBRARY__": "the interpreter's Tk library path",
}


class BatchActivator(ViaTemplateActivator):
    @classmethod
    def supports(cls, interpreter: PythonInfo) -> bool:
        return interpreter.os == "nt"

    def templates(self) -> Iterator[str]:
        yield "activate.bat"
        yield "deactivate.bat"
        yield "pydoc.bat"

    def generate(self, creator: Creator) -> list[Path]:
        values = super().replacements(creator, creator.bin_dir)
        problems = [reason for key in _PATH_REPLACEMENT_NAMES if (reason := _unsafe_path_reason(key, values[key]))]
        if problems:
            for problem in problems:
                LOGGER.warning("skipping batch activation scripts: %s", problem)
            return []
        return super().generate(creator)

    @staticmethod
    def quote(string: str) -> str:
        """Make a value safe to sit inside ``@set "VAR=value"``.

        Batch has no escape for a double quote in this context either: it always closes the quoted string, and whatever
        follows on the line runs as live cmd.exe syntax. A raw line boundary is worse - batch is line-oriented
        regardless of quote state, so it starts a brand-new statement instead of staying inside the value. None of these
        can be represented literally here, so replace them with a space. ``%`` still triggers variable expansion inside
        the quotes, but doubling it to ``%%`` is a real, in-file escape that keeps the literal character.

        """
        string = string.replace("%", "%%")
        for operator in _CMD_OPERATORS:
            string = string.replace(operator, " ")
        return collapse_line_boundaries(string)

    def instantiate_template(self, replacements: dict[str, str], template: str, creator: Creator) -> str:
        # ensure the text has all newlines as \r\n - required by batch
        base = super().instantiate_template(replacements, template, creator)
        return base.replace(os.linesep, "\n").replace("\n", os.linesep)


def _unsafe_path_reason(key: str, value: str) -> str | None:
    found = sorted({char for char in value if char in _PATH_UNSAFE_CHARS})
    if not found:
        return None
    return (
        f"{_PATH_REPLACEMENT_NAMES[key]} ({value!r}) contains {''.join(found)!r}, which the batch activator "
        "cannot preserve in generated scripts"
    )


__all__ = [
    "BatchActivator",
]
