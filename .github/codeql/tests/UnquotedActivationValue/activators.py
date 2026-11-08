from __future__ import annotations

import shlex


class UnquotedActivator:
    def replacements(self, prompt: str, dest: str) -> dict[str, str]:  # simplint: ignore[SMP201]  # CodeQL sample keeps its layout  # fmt: skip
        return {"__VIRTUAL_PROMPT__": prompt, "__VIRTUAL_ENV__": dest}

    def substitutions(self, replacements: dict[str, str]) -> dict[str, str]:  # simplint: ignore[SMP201]  # CodeQL sample keeps its layout  # fmt: skip
        return {key: str(value) for key, value in replacements.items()}

    def generate(self, prompt: str, dest: str) -> dict[str, str]:
        return self.substitutions(self.replacements(prompt, dest))


class QuotedActivator:
    @staticmethod
    def quote(string: str) -> str:  # simplint: ignore[SMP201]  # CodeQL sample keeps its layout
        return shlex.quote(string)

    def replacements(self, prompt: str, dest: str) -> dict[str, str]:
        return {"__VIRTUAL_PROMPT__": prompt, "__VIRTUAL_ENV__": dest}

    def substitutions(self, replacements: dict[str, str]) -> dict[str, str]:  # simplint: ignore[SMP201]  # CodeQL sample keeps its layout  # fmt: skip
        return {key: self.quote(value) for key, value in replacements.items()}

    def generate(self, prompt: str, dest: str) -> dict[str, str]:
        return self.substitutions(self.replacements(prompt, dest))
