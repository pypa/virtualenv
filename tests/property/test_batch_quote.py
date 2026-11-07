from __future__ import annotations

from typing import Final

import pytest
from hypothesis import example, given
from hypothesis import strategies as st

from virtualenv.activation.batch import BatchActivator

pytestmark: Final[pytest.MarkDecorator] = pytest.mark.property

# Confirmed live syntax inside @set "VAR=value" on a real Windows runner, independently of this fix's
# own implementation - this is not just re-asserting quote()'s source. `!` only turns live when the
# caller already has delayed expansion enabled, but a crafted prompt then leaks the value of whatever
# variable it names, confirmed the same way.
_DANGEROUS: Final[str] = '"&|<>^!'
_SAFE_IN_THIS_CONTEXT: Final[str] = "()"
_LINE_BOUNDARIES: Final[str] = f"\n\r\v\f\x1c\x1d\x1e\x85{chr(0x2028)}{chr(0x2029)}"

# Lone surrogates are excluded: cmd.exe scripts are read as text, and the same limit applies to the
# pyvenv.cfg property tests for the same reason.
values: Final[st.SearchStrategy[str]] = st.text(st.characters(blacklist_categories=("Cs",), max_codepoint=0x2100))


@given(value=values)
@example('x" & type nul > pwned.marker & "')  # the confirmed exploit payload
@example("x^& type nul ^> pwned.marker ^& ")  # caret-escaped: still live outside a quoted context
@example("x\n@type nul > pwned.marker\n@rem ")  # newline: a full extra statement, not just a breakout
@example('a"&type nul>pwned.marker&"b')
@example("foo!SECRET!bar")  # delayed-expansion variable substitution, confirmed under cmd /V:ON
def test_quote_strips_every_dangerous_character(value: str) -> None:
    quoted = BatchActivator.quote(value)

    assert not (set(quoted) & set(_DANGEROUS))
    assert not (set(quoted) & set(_LINE_BOUNDARIES))


@given(value=st.text(st.sampled_from(_SAFE_IN_THIS_CONTEXT), min_size=1))
@example("(x86)")  # the shape that shows up in every 32-bit "Program Files (x86)" install
def test_quote_leaves_parentheses_untouched(value: str) -> None:
    assert BatchActivator.quote(value) == value


@given(value=values)
def test_quote_keeps_percent_literal_and_balanced(value: str) -> None:
    """Every ``%`` must survive doubled, never as a lone character that triggers expansion."""
    quoted = BatchActivator.quote(value)

    assert quoted.replace("%%", "").count("%") == 0


@given(value=values)
@example('x" & type nul > pwned.marker & "')
def test_embedding_in_the_set_statement_stays_one_well_formed_line(value: str) -> None:
    """The exact shape the template uses: a single ``@set "VAR=value"`` statement."""
    rendered = f'@set "VIRTUAL_ENV_PROMPT={BatchActivator.quote(value)}"'

    assert rendered.count("\n") == 0
    assert rendered.count('"') == 2
