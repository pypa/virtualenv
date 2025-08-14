from __future__ import annotations

import os
import re

from virtualenv.activation.via_template import ViaTemplateActivator


class BatchActivator(ViaTemplateActivator):
    @classmethod
    def supports(cls, interpreter):
        return interpreter.os == "nt"

    def templates(self):
        yield "activate.bat"
        yield "deactivate.bat"
        yield "pydoc.bat"

    @staticmethod
    def quote(string):
        return string

    def instantiate_template(self, replacements, template, creator):
        # ensure the text has all newlines as \r\n - required by batch
        base = super().instantiate_template(replacements, template, creator)
        # escape & in VIRTUAL_ENV_PROMPT
        base = re.sub(
            r'(@set "VIRTUAL_ENV_PROMPT=)(.*?)(")',
            lambda m: m.group(1) + m.group(2).replace("&", "^&") + m.group(3),
            base,
            flags=re.MULTILINE,
        )
        return base.replace(os.linesep, "\n").replace("\n", os.linesep)


__all__ = [
    "BatchActivator",
]
