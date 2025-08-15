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
        if template == "activate.bat":
            # sanitize batch-special chars from key replacements
            safe_replacements = replacements.copy()
            safe_replacements["__VIRTUAL_ENV__"] = re.sub(r"[&<>|^]", "", replacements["__VIRTUAL_ENV__"])
            safe_replacements["__VIRTUAL_PROMPT__"] = re.sub(r"[&<>|^]", "", replacements["__VIRTUAL_PROMPT__"])
            base = super().instantiate_template(safe_replacements, template, creator)
            # DEBUG: print what we generated
            print(f"DEBUG SANITIZED VIRTUAL_ENV: {safe_replacements['__VIRTUAL_ENV__']}")
            print(f"DEBUG SANITIZED VIRTUAL_PROMPT: {safe_replacements['__VIRTUAL_PROMPT__']}")
            print("DEBUG FIRST 10 LINES OF ACTIVATE.BAT:")
            for i, line in enumerate(base.split('\n')[:10]):
                print(f"  {i+1}: {line}")
        else:
            base = super().instantiate_template(replacements, template, creator)
        return base.replace(os.linesep, "\n").replace("\n", os.linesep)


__all__ = [
    "BatchActivator",
]
