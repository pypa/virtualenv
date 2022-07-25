from pathlib import Path

from ..via_template import ViaTemplateActivator


class PowerShellActivator(ViaTemplateActivator):
    def templates(self):
        yield Path("activate.ps1")


__all__ = [
    "PowerShellActivator",
]
