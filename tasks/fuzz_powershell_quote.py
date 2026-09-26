"""Fuzz PowerShellActivator.quote for crashes and correct single-quote escaping.

Run directly: python tasks/fuzz_powershell_quote.py -runs=100000

"""

from __future__ import annotations

import sys
from typing import Final

import atheris
from fuzz_shared import consume_text

with atheris.instrument_imports(include=["virtualenv"]):
    from virtualenv.activation.powershell import PowerShellActivator

# PowerShell closes a single-quoted string on the ASCII apostrophe and on each curly single quote U+2018-U+201B
_DELIMITERS: Final[frozenset[str]] = frozenset("'\u2018\u2019\u201a\u201b")


@atheris.instrument_func
def test_one_input(data: bytes) -> None:
    string = consume_text(data)
    quoted = PowerShellActivator.quote(string)
    expected = "'" + "".join(char * 2 if char in _DELIMITERS else char for char in string) + "'"
    assert quoted == expected, (quoted, expected)  # ruff:ignore[assert] atheris treats AssertionError as the crash signal


if __name__ == "__main__":
    atheris.Setup(sys.argv, test_one_input)
    atheris.Fuzz()
