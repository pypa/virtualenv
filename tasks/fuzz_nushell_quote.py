"""Fuzz NushellActivator.quote for crashes and correct raw-string escaping.

Run directly: python tasks/fuzz_nushell_quote.py -runs=100000

"""

from __future__ import annotations

import sys

import atheris
from fuzz_shared import consume_text

with atheris.instrument_imports(include=["virtualenv"]):
    from virtualenv.activation.nushell import NushellActivator


@atheris.instrument_func
def test_one_input(data: bytes) -> None:
    string = consume_text(data)
    quoted = NushellActivator.quote(string)
    wrapping = "#" * (_longest_run(string, "#") + 1)
    expected = f"r{wrapping}'{string}'{wrapping}"
    assert quoted == expected, (quoted, expected)  # ruff:ignore[assert] atheris treats AssertionError as the crash signal


def _longest_run(string: str, char: str) -> int:
    current = longest = 0
    for c in string:
        current = current + 1 if c == char else 0
        longest = max(longest, current)
    return longest


if __name__ == "__main__":
    atheris.Setup(sys.argv, test_one_input)
    atheris.Fuzz()
