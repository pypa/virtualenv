from __future__ import annotations

import shlex


class UnquotedActivator:
    def replacements(self, prompt: str, dest: str) -> dict[str, str]:
        return {"__VIRTUAL_PROMPT__": prompt, "__VIRTUAL_ENV__": dest}

    def instantiate_template(self, text: str, prompt: str, dest: str) -> str:
        for key, value in self.replacements(prompt, dest).items():
            text = text.replace(key, value)
        return text


class QuotedActivator:
    @staticmethod
    def quote(string: str) -> str:
        return shlex.quote(string)

    def replacements(self, prompt: str, dest: str) -> dict[str, str]:
        return {"__VIRTUAL_PROMPT__": prompt, "__VIRTUAL_ENV__": dest}

    def instantiate_template(self, text: str, prompt: str, dest: str) -> str:
        for key, value in self.replacements(prompt, dest).items():
            text = text.replace(key, self.quote(value))
        return text
