from __future__ import absolute_import, unicode_literals

from pathlib2 import Path

from ..via_template import ViaTemplateActivator


class XonoshActivator(ViaTemplateActivator):
    def templates(self):
        yield Path("activate.xsh")

    @classmethod
    def supports(cls, interpreter):
        return True if interpreter.version_info >= (3, 4) else False