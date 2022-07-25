from pathlib import Path

from ..via_template import ViaTemplateActivator


class CShellActivator(ViaTemplateActivator):
    @classmethod
    def supports(cls, interpreter):
        return interpreter.os != "nt"

    def templates(self):
        yield Path("activate.csh")


__all__ = [
    "CShellActivator",
]
