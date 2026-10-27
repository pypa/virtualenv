from __future__ import annotations

from argparse import Namespace
from typing import TYPE_CHECKING, Final

import pytest
from prompt_matrix import PROMPT_CASES, SHELLS, generate_script, prompt_shown, run_prompt, unavailable

from virtualenv.activation.activator import Activator

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.graalpy
def test_activator_prompt_cwd(monkeypatch, tmp_path) -> None:
    class FakeActivator(Activator):
        def generate(self, creator):
            raise NotImplementedError

    cwd = tmp_path / "magic"
    cwd.mkdir()
    monkeypatch.chdir(cwd)

    activator = FakeActivator(Namespace(prompt="."))
    assert activator.flag_prompt == "magic"


@pytest.mark.slow
@pytest.mark.parametrize("case", PROMPT_CASES, ids=["-".join(case) for case in PROMPT_CASES])
def test_activator_prompt_stays_data(tmp_path: Path, case: tuple[str, str, str, str]) -> None:
    shell, state, action, payload = case
    if reason := unavailable(shell, action):
        pytest.skip(reason)
    prompt: Final = SHELLS[shell].payloads[payload]
    result: Final = run_prompt(shell, generate_script(shell, tmp_path / "env", prompt), state, action, tmp_path)

    assert ((tmp_path / "PWNED").exists(), prompt_shown(shell, result, prompt, state, action)) == (False, True), (
        result.stdout + result.stderr
    )
