from __future__ import annotations


class XonshActivator:
    @staticmethod
    def quote(string: str) -> str:
        return repr(string)


class PythonActivator:
    @staticmethod
    def quote(string: str) -> str:
        return ascii(string)
