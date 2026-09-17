"""Property tests for the pyvenv.cfg reader and writer.

pyvenv.cfg is a line-based format with no escape syntax, so the invariant that matters is that a value can never be read
back as extra configuration. These properties are what caught #3247: a prompt containing a line boundary used to inject
arbitrary keys, overriding any key written before it, including ``home``.

"""

from __future__ import annotations

import os
from collections import OrderedDict

import pytest
from hypothesis import example, given
from hypothesis import strategies as st

from virtualenv.create.pyenv_cfg import PyEnvCfg

pytestmark = pytest.mark.property

# Anything str.splitlines() treats as a boundary is what makes a value escape its own line.
LINE_BOUNDARIES = "\n\r\v\f\x1c\x1d\x1e\x85" + chr(0x2028) + chr(0x2029)

# Lone surrogates are excluded throughout: the file is UTF-8, so they cannot be written at all, and
# the same is true of the stdlib venv. That is a limit of the format rather than of this code.
printable = st.characters(blacklist_categories=("Cs",), max_codepoint=0x2100)

keys = st.text(
    st.characters(blacklist_categories=("Cs",), blacklist_characters="=" + LINE_BOUNDARIES), min_size=1
).filter(lambda k: k.strip() == k and not k.startswith("#"))
contents = st.dictionaries(keys, st.text(printable), max_size=6)


def _round_trip(content: dict[str, str], tmp_path) -> dict[str, str]:
    path = tmp_path / "pyvenv.cfg"
    PyEnvCfg(OrderedDict(content), path).write()
    return dict(PyEnvCfg.from_file(path).content)


@given(content=contents)
@example(content={"prompt": 'x"\nhome = /attacker\nprompt = "z'})
@example(content={"prompt": "a" + chr(0x2028) + "home = /attacker"})
@example(content={"home": "a\r\nevil = 1"})
def test_writing_then_reading_never_invents_keys(content, tmp_path_factory) -> None:
    """A value must never be read back as a new configuration key."""
    read_back = _round_trip(content, tmp_path_factory.mktemp("cfg"))

    assert set(read_back) <= set(content)


@given(content=contents)
@example(content={"prompt": 'x"\nhome = /attacker\nprompt = "z'})
def test_written_file_has_one_line_per_key(content, tmp_path_factory) -> None:
    """However exotic the values, the file keeps its line-per-key shape."""
    path = tmp_path_factory.mktemp("cfg") / "pyvenv.cfg"
    PyEnvCfg(OrderedDict(content), path).write()

    lines = path.read_text(encoding="utf-8").splitlines()

    assert len(lines) == len(content)
    assert all(" = " in line for line in lines)


@given(
    content=st.dictionaries(
        keys,
        st.text(st.characters(blacklist_categories=("Cs",), blacklist_characters=LINE_BOUNDARIES), min_size=1).filter(
            # write() rewrites a value naming an existing path, which is deliberate and not under test.
            lambda v: v.strip() == v and v[0] not in "'\"" and v[-1] not in "'\"" and not os.path.exists(v)
        ),
        max_size=6,
    )
)
def test_plain_values_round_trip_unchanged(content, tmp_path_factory) -> None:
    """A value that the format can represent comes back exactly as written."""
    assert _round_trip(content, tmp_path_factory.mktemp("cfg")) == content
