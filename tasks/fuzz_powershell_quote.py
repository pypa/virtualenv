"""Fuzz PowerShellActivator.quote for crashes and correct single-quote escaping.

Run directly: python tasks/fuzz_powershell_quote.py -runs=100000

"""

from __future__ import annotations

import sys

import atheris
from fuzz_shared import consume_text

with atheris.instrument_imports(include=["virtualenv"]):
    from virtualenv.activation.powershell import PowerShellActivator


@atheris.instrument_func
def test_one_input(data: bytes) -> None:
    string = consume_text(data)
    quoted = PowerShellActivator.quote(string)
    expected = f"'{string.replace(chr(39), chr(39) * 2)}'"
    assert quoted == expected, (quoted, expected)  # ruff:ignore[assert] atheris treats AssertionError as the crash signal


if __name__ == "__main__":
    atheris.Setup(sys.argv, test_one_input)
    atheris.Fuzz()
