from __future__ import absolute_import, unicode_literals

from virtualenv.util.path import Path

from ..via_template import ViaTemplateActivator


class FishActivator(ViaTemplateActivator):
    def templates(self):
        yield Path("activate.fish")

    @classmethod
    def supports(cls, interpreter):
        return interpreter.os != "nt"
