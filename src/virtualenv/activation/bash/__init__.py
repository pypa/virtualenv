from __future__ import annotations

from pathlib import Path  # fmt: skip
from typing import TYPE_CHECKING  # fmt: skip

from virtualenv.activation.via_template import ViaTemplateActivator  # isort: skip # fmt: skip

if TYPE_CHECKING:
    from collections.abc import Iterator

    from virtualenv.create.creator import Creator


class BashActivator(ViaTemplateActivator):  # fmt: skip
    """Generate the ``activate`` script for POSIX Bourne-compatible shells."""

    def templates(self) -> Iterator[str]:
        """The template file names to instantiate.

        :yields: the template file names

        """
        yield "activate.sh"

    def as_name(self, template: str) -> str:
        """The file name of the generated script, the template name without its suffix.

        :param template: the name of the template file

        :returns: the name of the generated script

        """
        return Path(template).stem

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
    "BashActivator",
]
