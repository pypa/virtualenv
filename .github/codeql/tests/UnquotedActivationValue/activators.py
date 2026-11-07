from __future__ import annotations

import shlex


class UnquotedActivator:
    def generate(self, prompt: str, dest: str) -> dict[str, str]:
        return self.substitutions(self.replacements(prompt, dest))

    def substitutions(self, replacements: dict[str, str]) -> dict[str, str]:
        return {key: str(value) for key, value in replacements.items()}

    def replacements(self, prompt: str, dest: str) -> dict[str, str]:
        return {"__VIRTUAL_PROMPT__": prompt, "__VIRTUAL_ENV__": dest}


class QuotedActivator:
    def generate(self, prompt: str, dest: str) -> dict[str, str]:
        return self.substitutions(self.replacements(prompt, dest))

    def substitutions(self, replacements: dict[str, str]) -> dict[str, str]:
        return {key: self.quote(value) for key, value in replacements.items()}

    @staticmethod
    def quote(string: str) -> str:
        return shlex.quote(string)

    def replacements(self, prompt: str, dest: str) -> dict[str, str]:
        return {"__VIRTUAL_PROMPT__": prompt, "__VIRTUAL_ENV__": dest}
