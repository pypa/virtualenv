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
        if template == "activate.bat":
            # only sanitize the prompt placeholder
            # __VIRTUAL_PROMPT__ → VIRTUAL_ENV_PROMPT
            safe = replacements["__VIRTUAL_PROMPT__"]
            safe = re.sub(r"(?<!\r)\n", "\r\n", safe)
            base = base.replace(f'"{replacements["__VIRTUAL_PROMPT__"]}"', f'"{safe}"')
        return base.replace(os.linesep, "\n").replace("\n", os.linesep)


__all__ = [
    "BatchActivator",
]
