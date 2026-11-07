from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

from virtualenv.activation.via_template import ViaTemplateActivator

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

    from virtualenv.create.creator import Creator


class XonshActivator(ViaTemplateActivator):
    def generate(self, creator: Creator) -> list[Path]:
        if re.search(r"\$(?:\w+|{)|=~", str(creator.dest)):
            logging.getLogger(__name__).warning(
                "skipping xonsh activation script: destination %s contains path expansion syntax", creator.dest
            )
            (creator.bin_dir / "activate.xsh").unlink(missing_ok=True)
            return []
        return super().generate(creator)

    def templates(self) -> Iterator[str]:
        yield "activate.xsh"

    @staticmethod
    def quote(string: str) -> str:
        """Keep literals independent of the encoding xonsh uses to read the script."""
        return ascii(string)

    def replacements(self, creator: Creator, dest_folder: Path) -> dict[str, str]:
        data = super().replacements(creator, dest_folder)
        data.update({
            "__TCL_LIBRARY__": getattr(creator.interpreter, "tcl_lib", None) or "",
            "__TK_LIBRARY__": getattr(creator.interpreter, "tk_lib", None) or "",
        })
        return data


__all__ = [
    "XonshActivator",
]
