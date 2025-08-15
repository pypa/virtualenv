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
            # Sanitize ONLY the prompt (with_prompt case)
            safe_replacements["__VIRTUAL_PROMPT__"] = re.sub(
                r"[&<>|^]", "", replacements["__VIRTUAL_PROMPT__"]
            )

            # For no_prompt case, sanitize the fallback name
            if not safe_replacements["__VIRTUAL_PROMPT__"]:
                safe_name = re.sub(
                    r"[&<>|^]", "", os.path.basename(replacements["__VIRTUAL_ENV__"])
                )
                safe_replacements["__VIRTUAL_PROMPT__"] = safe_name
            base = super().instantiate_template(safe_replacements, template, creator)
        else:
            base = super().instantiate_template(replacements, template, creator)
        return base.replace(os.linesep, "\n").replace("\n", os.linesep)


__all__ = [
    "BatchActivator",
]
