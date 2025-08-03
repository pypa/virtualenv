from __future__ import annotations

import os
import sys
from argparse import Namespace

import pytest

from virtualenv.activation import FishActivator
from virtualenv.info import IS_WIN


@pytest.mark.parametrize(
    ("tcl_lib", "tk_lib", "present"),
    [
        ("/path/to/tcl", "/path/to/tk", True),
        (None, None, False),
    ],
)
def test_fish_tkinter_generation(tmp_path, tcl_lib, tk_lib, present):
    # GIVEN
    class MockInterpreter:
        pass

    interpreter = MockInterpreter()
    interpreter.tcl_lib = tcl_lib
    interpreter.tk_lib = tk_lib

    class MockCreator:
        def __init__(self, dest):
            self.dest = dest
            self.bin_dir = dest / "bin"
            self.bin_dir.mkdir()
            self.interpreter = interpreter
            self.pyenv_cfg = {}
            self.env_name = "my-env"

    creator = MockCreator(tmp_path)
    options = Namespace(prompt=None)
    activator = FishActivator(options)

    # WHEN
    activator.generate(creator)
    content = (creator.bin_dir / "activate.fish").read_text(encoding="utf-8")

    # THEN
    if present:
        assert "set -gx TCL_LIBRARY '/path/to/tcl'" in content
        assert "set -gx TK_LIBRARY '/path/to/tk'" in content
    else:
        assert "if test -n ''\n  if set -q TCL_LIBRARY;" in content
        assert "if test -n ''\n  if set -q TK_LIBRARY;" in content


@pytest.mark.skipif(IS_WIN, reason="we have not setup fish in CI yet")
def test_fish(activation_tester_class, activation_tester, monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    fish_conf_dir = tmp_path / ".config" / "fish"
    fish_conf_dir.mkdir(parents=True)
    (fish_conf_dir / "config.fish").write_text("", encoding="utf-8")

    class Fish(activation_tester_class):
        def __init__(self, session) -> None:
            super().__init__(FishActivator, session, "fish", "activate.fish", "fish")

        def print_prompt(self):
            return "fish_prompt"

        def _get_test_lines(self, activate_script):
            return [
                self.print_python_exe(),
                self.print_os_env_var("VIRTUAL_ENV"),
                self.print_os_env_var("VIRTUAL_ENV_PROMPT"),
                self.print_os_env_var("PATH"),
                self.activate_call(activate_script),
                self.print_python_exe(),
                self.print_os_env_var("VIRTUAL_ENV"),
                self.print_os_env_var("VIRTUAL_ENV_PROMPT"),
                self.print_os_env_var("PATH"),
                self.print_prompt(),
                # \\ loads documentation from the virtualenv site packages
                self.pydoc_call,
                self.deactivate,
                self.print_python_exe(),
                self.print_os_env_var("VIRTUAL_ENV"),
                self.print_os_env_var("VIRTUAL_ENV_PROMPT"),
                self.print_os_env_var("PATH"),
                "",  # just finish with an empty new line
            ]

        def assert_output(self, out, raw, _):
            """Compare _get_test_lines() with the expected values."""
            assert out[0], raw
            assert out[1] == "None", raw
            assert out[2] == "None", raw
            # self.activate_call(activate_script) runs at this point
            expected = self._creator.exe.parent / os.path.basename(sys.executable)
            assert self.norm_path(out[4]) == self.norm_path(expected), raw
            assert self.norm_path(out[5]) == self.norm_path(self._creator.dest).replace("\\\\", "\\"), raw
            assert out[6] == self._creator.env_name
            # Some attempts to test the prompt output print more than 1 line.
            # So we need to check if the prompt exists on any of them.
            prompt_text = f"({self._creator.env_name}) "
            assert any(prompt_text in line for line in out[7:-5]), raw

            assert out[-5] == "wrote pydoc_test.html", raw
            content = tmp_path / "pydoc_test.html"
            assert content.exists(), raw
            # post deactivation, same as before
            assert out[-4] == out[0], raw
            assert out[-3] == "None", raw
            assert out[-2] == "None", raw

            # Check that the PATH is restored
            assert out[3] == out[13], raw
            # Check that PATH changed after activation
            assert out[3] != out[8], raw

    activation_tester(Fish)
