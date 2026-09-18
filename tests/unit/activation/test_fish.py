from __future__ import annotations

import os
import shlex
import shutil
import subprocess
import sys
from argparse import Namespace
from types import SimpleNamespace
from typing import TYPE_CHECKING

import pytest

from virtualenv.activation import FishActivator
from virtualenv.info import IS_WIN
from virtualenv.run import cli_run

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

FISH = shutil.which("fish")


@pytest.fixture
def rendered_activate_fish(tmp_path: Path) -> Callable[[str | None, str | None], Path]:
    def render(tcl_lib: str | None, tk_lib: str | None) -> Path:
        creator = SimpleNamespace(
            dest=tmp_path,
            bin_dir=tmp_path / "bin",
            interpreter=SimpleNamespace(tcl_lib=tcl_lib, tk_lib=tk_lib),
            pyenv_cfg={},
            env_name="my-env",
        )
        creator.bin_dir.mkdir()
        FishActivator(Namespace(prompt=None)).generate(creator)
        return creator.bin_dir / "activate.fish"

    return render


@pytest.mark.parametrize(
    ("tcl_lib", "tk_lib", "present"),
    [
        ("/path/to/tcl", "/path/to/tk", True),
        ("/Program Files/tcl", "/Program Files/tk", True),
        (None, None, False),
    ],
)
def test_fish_tkinter_generation(
    rendered_activate_fish: Callable[[str | None, str | None], Path],
    tcl_lib: str | None,
    tk_lib: str | None,
    present: bool,
) -> None:
    content = rendered_activate_fish(tcl_lib, tk_lib).read_text(encoding="utf-8")

    assert 'set -gx _OLD_PKG_CONFIG_PATH "$PKG_CONFIG_PATH"' in content
    assert 'set -gx PKG_CONFIG_PATH "$VIRTUAL_ENV/lib/pkgconfig:$PKG_CONFIG_PATH"' in content
    assert "set -e _OLD_PKG_CONFIG_PATH" in content

    if present:
        assert f"set -gx TCL_LIBRARY {shlex.quote(tcl_lib)}\n" in content
        assert f"set -gx TK_LIBRARY {shlex.quote(tk_lib)}\n" in content
    else:
        assert "if test -n ''\n  set -gx _OLD_VIRTUAL_TCL_LIBRARY" in content
        assert "if test -n ''\n  set -gx _OLD_VIRTUAL_TK_LIBRARY" in content


@pytest.mark.skipif(IS_WIN, reason="fish is not available on Windows")
@pytest.mark.skipif(FISH is None, reason="fish is not installed")
def test_fish_tkinter_path_does_not_run_commands(
    rendered_activate_fish: Callable[[str | None, str | None], Path], tmp_path: Path
) -> None:
    marker = tmp_path / "PWNED"
    script = rendered_activate_fish(f"/tcl/(touch {marker})/lib", "/tk/lib")

    subprocess.run([FISH, "-c", f"source '{script}'"], capture_output=True, text=True, timeout=60, check=False)

    assert not marker.exists()


@pytest.mark.skipif(IS_WIN, reason="fish is not available on Windows")
@pytest.mark.skipif(FISH is None, reason="fish is not installed")
@pytest.mark.parametrize(
    ("original", "expected"),
    [
        pytest.param("", "", id="empty"),
        # fish joins a path variable with colons when it is expanded inside quotes
        pytest.param("/usr/bin /bin", "/usr/bin:/bin", id="populated"),
    ],
)
def test_fish_deactivate_restores_path(tmp_path, current_fastest, original, expected) -> None:
    dest = tmp_path / "venv"
    cli_run([
        "--without-pip",
        str(dest),
        "--creator",
        current_fastest,
        "--no-periodic-update",
        "--activators",
        "fish",
    ])

    out = subprocess.run(
        [
            FISH,
            "--no-config",
            "-c",
            f"set -gx PATH {original}\nsource '{dest / 'bin' / 'activate.fish'}'\ndeactivate\necho \"PATH=<$PATH>\"\n",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
        check=False,
    ).stdout

    assert out == f"PATH=<{expected}>\n"


@pytest.mark.skipif(IS_WIN, reason="fish is not available on Windows")
@pytest.mark.skipif(FISH is None, reason="fish is not installed")
def test_fish_prompt_survives_shadowed_source(activation_python, tmp_path) -> None:
    # A user function shadowing `.`/`source` must not hijack the prompt's exit-status restore. Source a copy of the
    # rendered script from an ASCII path so the driver avoids the venv path's special characters.
    script = tmp_path / "activate.fish"
    rendered = activation_python.creator.bin_dir / "activate.fish"
    script.write_text(rendered.read_text(encoding="utf-8"), encoding="utf-8")
    start, trap = tmp_path / "start", tmp_path / "trap"
    start.mkdir()
    trap.mkdir()
    driver = tmp_path / "driver.fish"
    driver.write_text(
        f"cd '{start}'\nfunction . ; cd '{trap}' ; end\nsource '{script}'\nfish_prompt\necho \"PWD=$PWD\"\n",
        encoding="utf-8",
    )
    out = subprocess.run(
        [FISH, str(driver)], capture_output=True, text=True, encoding="utf-8", timeout=60, check=True
    ).stdout
    assert f"PWD={start}\n" in out, out


@pytest.mark.slow
@pytest.mark.skipif(IS_WIN, reason="we have not setup fish in CI yet")
def test_fish(activation_tester_class, activation_tester, monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    fish_conf_dir = tmp_path / ".config" / "fish"
    fish_conf_dir.mkdir(parents=True)
    (fish_conf_dir / "config.fish").write_text("", encoding="utf-8")

    class Fish(activation_tester_class):
        def __init__(self, session) -> None:
            super().__init__(FishActivator, session, "fish", "activate.fish", "fish")

        def print_prompt(self) -> str:
            return "fish_prompt"

        def _get_test_lines(self, activate_script):
            return [
                self.print_python_exe(),
                self.print_os_env_var("VIRTUAL_ENV"),
                self.print_os_env_var("VIRTUAL_ENV_PROMPT"),
                self.print_os_env_var("PATH"),
                self.print_os_env_var("TCL_LIBRARY"),
                self.print_os_env_var("TK_LIBRARY"),
                self.print_os_env_var("PKG_CONFIG_PATH"),
                self.activate_call(activate_script),
                self.print_python_exe(),
                self.print_os_env_var("VIRTUAL_ENV"),
                self.print_os_env_var("VIRTUAL_ENV_PROMPT"),
                self.print_os_env_var("PATH"),
                self.print_os_env_var("TCL_LIBRARY"),
                self.print_os_env_var("TK_LIBRARY"),
                self.print_os_env_var("PKG_CONFIG_PATH"),
                self.print_prompt(),
                # \\ loads documentation from the virtualenv site packages
                self.pydoc_call,
                self.deactivate,
                self.print_python_exe(),
                self.print_os_env_var("VIRTUAL_ENV"),
                self.print_os_env_var("VIRTUAL_ENV_PROMPT"),
                self.print_os_env_var("PATH"),
                self.print_os_env_var("TCL_LIBRARY"),
                self.print_os_env_var("TK_LIBRARY"),
                self.print_os_env_var("PKG_CONFIG_PATH"),
                "",  # just finish with an empty new line
            ]

        def assert_output(self, out, raw, _) -> None:
            """Compare _get_test_lines() with the expected values."""
            assert out[0], raw
            assert out[1] == "None", raw
            assert out[2] == "None", raw
            self.assert_tcl_tk_library(out[4:6], out[11:13], out[-3:-1], raw)
            self.assert_pkg_config_path(out[6], out[13], out[-1], raw)
            # self.activate_call(activate_script) runs at this point
            expected = self._creator.exe.parent / os.path.basename(sys.executable)
            assert self.norm_path(out[7]) == self.norm_path(expected), raw
            assert self.norm_path(out[8]) == self.norm_path(self._creator.dest).replace("\\\\", "\\"), raw
            assert out[9] == self._creator.env_name
            # Some attempts to test the prompt output print more than 1 line.
            # So we need to check if the prompt exists on any of them.
            prompt_text = f"({self._creator.env_name}) "
            assert any(prompt_text in line for line in out[14:-8]), raw

            assert out[-8] == "wrote pydoc_test.html", raw
            content = tmp_path / "pydoc_test.html"
            assert content.exists(), raw
            # post deactivation, same as before
            assert out[-7] == out[0], raw
            assert out[-6] == "None", raw
            assert out[-5] == "None", raw

            # Check that the PATH is restored
            assert out[3] == out[-4], raw
            # Check that PATH changed after activation
            assert out[3] != out[10], raw

    activation_tester(Fish)
