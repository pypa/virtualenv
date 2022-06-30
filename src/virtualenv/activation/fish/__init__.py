from pathlib import Path

from ..via_template import ViaTemplateActivator


class FishActivator(ViaTemplateActivator):
    def templates(self):
        yield Path("activate.fish")


__all__ = [
    "FishActivator",
]
