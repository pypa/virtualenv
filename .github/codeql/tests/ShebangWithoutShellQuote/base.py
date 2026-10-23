from __future__ import annotations

from virtualenv.seed.embed.via_app_data.pip_install.base import shell_shebang


class ScriptMaker:
    def _build_shebang(self, executable: bytes, post_interp: bytes) -> bytes:
        return b"#!" + executable + post_interp


class PlainScriptMaker(ScriptMaker):
    def _build_shebang(self, executable: bytes, post_interp: bytes) -> bytes:
        return super()._build_shebang(executable, post_interp)


class QuotedScriptMaker(ScriptMaker):
    def _build_shebang(self, executable: bytes, post_interp: bytes) -> bytes:
        return shell_shebang(executable.decode(), post_interp)
