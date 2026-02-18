from __future__ import annotations

from argparse import Namespace

import pytest

from virtualenv.activation.activator import Activator


@pytest.mark.graalpy
def test_activator_prompt_cwd(monkeypatch, tmp_path):
    class FakeActivator(Activator):
        def generate(self, creator):
            raise NotImplementedError

    cwd = tmp_path / "magic"
    cwd.mkdir()
    monkeypatch.chdir(cwd)

    activator = FakeActivator(Namespace(prompt="."))
    assert activator.flag_prompt == "magic"
