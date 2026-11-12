from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING, Final

from virtualenv.activation.via_template import ViaTemplateActivator

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

    from virtualenv.create.creator import Creator


_GENERATE_PATTERN: Final[re.Pattern[str]] = re.compile(r"\$(?:\w+|{)|=~")


class XonshActivator(ViaTemplateActivator):
    """Generate the ``activate.xsh`` script for xonsh."""

    def generate(self, creator: Creator) -> list[Path]:
        """Generate the script, or remove it when the destination holds xonsh path expansion syntax.

        :param creator: the creator of the environment

        :returns: the paths of the generated scripts, empty when the destination is skipped

        """
        if _GENERATE_PATTERN.search(str(creator.dest)):
            logging.getLogger(__name__).warning(
                "skipping xonsh activation script: destination %s contains path expansion syntax", creator.dest
            )
            (creator.bin_dir / "activate.xsh").unlink(missing_ok=True)
            return []
        return super().generate(creator)

    def templates(self) -> Iterator[str]:
        """The template file names to instantiate.

        :yields: the template file names

        """
        yield "activate.xsh"

    @staticmethod
    def quote(string: str) -> str:
        """Keep literals independent of the encoding xonsh uses to read the script.

        :param string: the value to quote

        :returns: the ASCII-only literal representation of the string

        """
        return ascii(string)

    def replacements(self, creator: Creator, dest_folder: Path) -> dict[str, str]:
        """The raw placeholder values, including the Tcl and Tk library paths.

        :param creator: the creator of the environment
        :param dest_folder: the folder the scripts are written into

        :returns: the placeholder names mapped to their values

        """
        data = super().replacements(creator, dest_folder)
        data.update({
            "__TCL_LIBRARY__": getattr(creator.interpreter, "tcl_lib", None) or "",
            "__TK_LIBRARY__": getattr(creator.interpreter, "tk_lib", None) or "",
        })
        return data


__all__ = [
    "XonshActivator",
]
