"""Property tests for every activator's prompt across the prompt states and later actions its shell can reach.

The strategy builds prompts from tokens rather than characters, so a search without coverage feedback reaches the shapes
that matter: a backslash in front of a dollar sign or a backtick, a quote, a parameter expansion, and the marker command
of the shell under test. Each example runs every state and later action of that shell from the shared matrix, and must
neither create the marker file nor show the prompt differently from the shell's display rule.

"""

from __future__ import annotations

import tempfile
from itertools import product
from pathlib import Path
from typing import Final

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from prompt_matrix import PROMPT_PAYLOADS, SHELLS, generate_script, prompt_shown, run_prompt, unavailable

# each example launches the shell once per state and later action, so 60 PowerShell examples alone run past the suite's
# 120 second per-test timeout
pytestmark = [pytest.mark.property, pytest.mark.timeout(900)]


@pytest.mark.parametrize("shell", list(SHELLS))
@given(data=st.data())
@settings(max_examples=60, deadline=None)
def test_prompt_stays_data(shell: str, data: st.DataObject) -> None:
    if reason := unavailable(shell, "none"):
        pytest.skip(reason)
    _check_every_state(shell, data.draw(_prompt_values(shell)))


@pytest.mark.parametrize("shell", list(SHELLS))
def test_prompt_seeds_stay_data(shell: str) -> None:
    if reason := unavailable(shell, "none"):
        pytest.skip(reason)
    seeds: Final = {
        "bash": [
            PROMPT_PAYLOADS["backslash-dollar"],
            PROMPT_PAYLOADS["two-backslashes-dollar"],
            PROMPT_PAYLOADS["backslash-backtick"],
        ],
        "zsh": [PROMPT_PAYLOADS["backslash-dollar"], PROMPT_PAYLOADS["backslash-backtick"], "x%ny"],
        "fish": [PROMPT_PAYLOADS["fish-backslash-quote"], "x(touch PWNED)y"],
        "cshell": [PROMPT_PAYLOADS["command-substitution"], PROMPT_PAYLOADS["backticks"]],
        "nushell": ["x(touch PWNED)y"],
        "powershell": ["x$(New-Item PWNED)y"],
        "xonsh": ["x@(touch PWNED)y", "{RED}x"],
        "batch": ["x&type nul > PWNED&y", "x%PWNED%y", "x!PWNED!y"],
    }
    for seed in seeds[shell]:
        _check_every_state(shell, seed)


def _prompt_values(shell: str) -> st.SearchStrategy[str]:
    common: Final = ["\\", "x", "${", "}", "'", '"', "%", "!", "(", ")", ";", "é"]
    tokens: Final = {
        "bash": [*common, "$(touch PWNED)", "`touch PWNED`"],
        "zsh": [*common, "$(touch PWNED)", "`touch PWNED`"],
        "fish": [*common, "$(touch PWNED)", "(touch PWNED)", "\\'"],
        "cshell": [*common, "$(touch PWNED)", "`touch PWNED`"],
        "nushell": [*common, "(touch PWNED)"],
        "powershell": [*common, "$(New-Item PWNED)"],
        "xonsh": [*common, "@(touch PWNED)", "{env_name}", "{RED}"],
        # cmd.exe draws under the console code page, which the activator cannot choose, so the non-ASCII token stays out
        "batch": [
            *(token for token in common if token not in {"${", "}", "'", "é"}),
            "%PWNED%",
            "!PWNED!",
            "&type nul > PWNED&",
            "$P$$",
        ],
    }
    return st.lists(st.sampled_from(tokens[shell]), min_size=1, max_size=6).map("".join)


def _check_every_state(shell: str, prompt: str) -> None:
    spec: Final = SHELLS[shell]
    with tempfile.TemporaryDirectory() as tmp:
        root: Final = Path(tmp)
        script: Final = generate_script(shell, root / "env", prompt)
        for state, action in product(spec.states, spec.actions):
            if unavailable(shell, action):
                continue
            (cwd := root / f"{state}-{action}").mkdir()
            result = run_prompt(shell, script, state, action, cwd)
            observed = ((cwd / "PWNED").exists(), prompt_shown(shell, result, prompt, state, action))
            assert observed == (False, True), (shell, state, action, prompt, result.stdout + result.stderr)
