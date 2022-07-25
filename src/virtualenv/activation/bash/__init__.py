from pathlib import Path

from ..via_template import ViaTemplateActivator


class BashActivator(ViaTemplateActivator):
    def templates(self):
        yield Path("activate.sh")

    def as_name(self, template):
        return template.stem


__all__ = [
    "BashActivator",
]
