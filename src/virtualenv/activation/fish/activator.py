from __future__ import annotations

import re
from typing import TYPE_CHECKING

from virtualenv.activation.via_template import ViaTemplateActivator

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

    from virtualenv.create.creator import Creator


class FishActivator(ViaTemplateActivator):
    def templates(self) -> Iterator[str]:
        yield "activate.fish"

    @staticmethod
    def quote(string: str) -> str:
        # Keep escapes beside ASCII quotes so legacy decoders cannot absorb them into a preceding multibyte character.
        return "'" + re.sub(r"[\\']", lambda match: f"'\\{match.group()}'", string) + "'"

    def replacements(self, creator: Creator, dest_folder: Path) -> dict[str, str]:
        data = super().replacements(creator, dest_folder)
        data.update({
            "__TCL_LIBRARY__": getattr(creator.interpreter, "tcl_lib", None) or "",
            "__TK_LIBRARY__": getattr(creator.interpreter, "tk_lib", None) or "",
        })
        return data


__all__ = [
    "FishActivator",
]
