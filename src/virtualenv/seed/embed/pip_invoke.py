from __future__ import absolute_import, unicode_literals

from .base_embed import BaseEmbed


class PipInvoke(BaseEmbed):
    def __init__(self, options):
        super(PipInvoke, self).__init__(options)

    def run(self, creator):
        if not self.enabled:
            return
