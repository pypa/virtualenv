from __future__ import absolute_import, unicode_literals

from pathlib2 import Path

from ..via_template import ViaTemplateActivator


class BashActivator(ViaTemplateActivator):
    @classmethod
    def supports(cls, interpreter):
        return interpreter.os != "nt"

    def templates(self):
        yield Path("activate.sh")
