from __future__ import absolute_import, unicode_literals

import json

from pathlib2 import Path

from ..via_template import ViaTemplateActivator


class PythonActivator(ViaTemplateActivator):
    def templates(self):
        yield Path("activate_this.py")

    def replacements(self, creator):
        replacements = super(PythonActivator, self).replacements(creator)
        replacements.update({"__SITE_PACKAGES__": json.dumps(list(str(i) for i in creator.site_packages))})
        return replacements
