from __future__ import annotations

import shlex
import shutil
import subprocess
import sys
from argparse import Namespace
from typing import TYPE_CHECKING

import pytest

from virtualenv.activation import BashActivator
from virtualenv.info import IS_WIN
from virtualenv.run import cli_run

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path


@pytest.mark.skipif(IS_WIN, reason="Github Actions ships with WSL bash")
@pytest.mark.parametrize(
    ("tcl_lib", "tk_lib", "present"),
    [
        ("/path/to/tcl", "/path/to/tk", True),
        (None, None, False),
    ],
)
def test_bash_tkinter_generation(tmp_path, tcl_lib, tk_lib, present) -> None:
    # GIVEN
    class MockInterpreter:
        pass

    interpreter = MockInterpreter()
    interpreter.tcl_lib = tcl_lib
    interpreter.tk_lib = tk_lib

    class MockCreator:
        def __init__(self, dest) -> None:
            self.dest = dest
            self.bin_dir = dest / "bin"
            self.bin_dir.mkdir()
            self.interpreter = interpreter
            self.pyenv_cfg = {}
            self.env_name = "my-env"

    creator = MockCreator(tmp_path)
    options = Namespace(prompt=None)
    activator = BashActivator(options)

    # WHEN
    activator.generate(creator)
    content = (creator.bin_dir / "activate").read_text(encoding="utf-8")

    # THEN
    # The teardown logic is always present in deactivate()
    assert "unset _OLD_VIRTUAL_TCL_LIBRARY" in content
    assert "unset _OLD_VIRTUAL_TK_LIBRARY" in content
    assert "unset _OLD_PKG_CONFIG_PATH" in content

    # PKG_CONFIG_PATH is always set
    assert '_OLD_PKG_CONFIG_PATH="${PKG_CONFIG_PATH:-}"' in content
    assert 'PKG_CONFIG_PATH="${VIRTUAL_ENV}/lib/pkgconfig${PKG_CONFIG_PATH:+:${PKG_CONFIG_PATH}}"' in content
    assert "export PKG_CONFIG_PATH" in content
    assert 'PKG_CONFIG_PATH="$_OLD_PKG_CONFIG_PATH"' in content

    if present:
        assert 'if [ /path/to/tcl != "" ]; then' in content
        assert "TCL_LIBRARY=/path/to/tcl" in content
        assert "export TCL_LIBRARY" in content

        assert 'if [ /path/to/tk != "" ]; then' in content
        assert "TK_LIBRARY=/path/to/tk" in content
        assert "export TK_LIBRARY" in content
    else:
        # When not present, the if condition is false, so the block is not executed
        assert "if [ '' != \"\" ]; then" in content, content
        assert "TCL_LIBRARY=''" in content
        # The export is inside the if, so this is fine
        assert "export TCL_LIBRARY" in content


@pytest.fixture
def bash_after_deactivate(tmp_path: Path, current_fastest: str) -> Callable[[str, str], str]:
    dest = tmp_path / "venv"
    cli_run([
        "--without-pip",
        str(dest),
        "--creator",
        current_fastest,
        "--no-periodic-update",
        "--activators",
        "bash",
    ])

    def probe(setup: str, report: str) -> str:
        # activation probes the platform with uname, which an emptied PATH can no longer find
        driver = (
            'uname_path=$(command -v uname)\nuname() { "$uname_path" "$@"; }\n'
            f'{setup}\nsource "$1"\ndeactivate\n{report}\n'
        )
        return subprocess.run(
            ["bash", "--noprofile", "--norc", "-s", "--", str(dest / "bin" / "activate")],
            input=driver,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=60,
            check=False,
        ).stdout

    return probe


@pytest.mark.skipif(IS_WIN, reason="Github Actions ships with WSL bash")
@pytest.mark.parametrize("original", [pytest.param("", id="empty"), pytest.param("/usr/bin:/bin", id="populated")])
def test_bash_deactivate_restores_path(bash_after_deactivate: Callable[[str, str], str], original: str) -> None:
    out = bash_after_deactivate(f"PATH='{original}'", r'printf "PATH=<%s>\n" "$PATH"')

    assert out == f"PATH=<{original}>\n"


@pytest.mark.skipif(IS_WIN, reason="Github Actions ships with WSL bash")
@pytest.mark.parametrize(
    ("setup", "expected"),
    [
        pytest.param("unset PS1", "unset", id="unset"),
        pytest.param("PS1=''", "unset", id="empty"),
        pytest.param("PS1='base$ '", "set:base$ ", id="populated"),
    ],
)
def test_bash_deactivate_restores_ps1(
    bash_after_deactivate: Callable[[str, str], str], setup: str, expected: str
) -> None:
    out = bash_after_deactivate(setup, r'printf "%s\n" "${PS1+set:}${PS1-unset}"')

    assert out == f"{expected}\n"


@pytest.fixture
def relocated_bash_venv(
    tmp_path: Path, current_fastest: str
) -> Callable[[str], tuple[subprocess.CompletedProcess[str], Path, Path]]:
    def source_after_move(name: str) -> tuple[subprocess.CompletedProcess[str], Path, Path]:
        original = tmp_path / name
        cli_run([
            "--without-pip",
            str(original),
            "--creator",
            current_fastest,
            "--no-periodic-update",
            "--activators",
            "bash",
        ])
        relocated = tmp_path / "relocated"
        shutil.move(original, relocated)
        work_dir = tmp_path / "workdir"
        work_dir.mkdir()
        result = subprocess.run(
            ["bash", "-c", f'source "{relocated / "bin" / "activate"}" 2>/dev/null && echo "$VIRTUAL_ENV"'],
            capture_output=True,
            text=True,
            cwd=str(work_dir),
            encoding="utf-8",
            check=False,
        )
        return result, relocated, work_dir

    return source_after_move


@pytest.mark.skipif(IS_WIN, reason="Github Actions ships with WSL bash")
@pytest.mark.parametrize(
    "name", [pytest.param("original", id="plain"), pytest.param("has(paren)and'quote", id="shell-metacharacters")]
)
def test_bash_activate_relocation_resolves_virtual_env(
    relocated_bash_venv: Callable[[str], tuple[subprocess.CompletedProcess[str], Path, Path]], name: str
) -> None:
    result, relocated, _ = relocated_bash_venv(name)

    assert result.returncode == 0
    assert result.stdout.strip() == str(relocated)


@pytest.mark.skipif(IS_WIN, reason="Github Actions ships with WSL bash")
@pytest.mark.parametrize(
    "payload",
    [
        pytest.param("x'$(id > PWNED)'y", id="command-substitution"),
        pytest.param("x'`id > PWNED`'y", id="backticks"),
        pytest.param("a';id > PWNED;'b", id="statement-separator"),
    ],
)
def test_bash_activate_relocation_does_not_run_path_commands(
    relocated_bash_venv: Callable[[str], tuple[subprocess.CompletedProcess[str], Path, Path]], payload: str
) -> None:
    _, _, work_dir = relocated_bash_venv(payload)

    assert not (work_dir / "PWNED").exists()


@pytest.mark.skipif(IS_WIN, reason="Github Actions ships with WSL bash")
def test_bash_activate_does_not_export_ps1(tmp_path, current_fastest) -> None:
    dest = tmp_path / "env"
    cli_run([
        "--without-pip",
        str(dest),
        "--creator",
        current_fastest,
        "--no-periodic-update",
        "--activators",
        "bash",
    ])
    activate_script = dest / "bin" / "activate"
    print_ps1 = f"{shlex.quote(sys.executable)} -c 'import os; print(os.environ.get(\"PS1\"))'"
    result = subprocess.run(
        [
            "bash",
            "-c",
            (f"unset PS1; PS1='base$ '; source \"{activate_script}\" && {print_ps1} && deactivate && {print_ps1}"),
        ],
        capture_output=True,
        encoding="utf-8",
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == ["None", "None"]


@pytest.mark.slow
@pytest.mark.skipif(IS_WIN, reason="Github Actions ships with WSL bash")
@pytest.mark.parametrize("hashing_enabled", [True, False])
def test_bash(raise_on_non_source_class, hashing_enabled, activation_tester) -> None:
    class Bash(raise_on_non_source_class):
        def __init__(self, session) -> None:
            super().__init__(
                BashActivator,
                session,
                "bash",
                "activate",
                "sh",
                "You must source this script: $ source ",
            )
            self.deactivate += " || exit 1"
            self._invoke_script.append("-h" if hashing_enabled else "+h")

        def activate_call(self, script):
            return super().activate_call(script) + " || exit 1"

        def print_prompt(self):
            return 'printf "%s\\n" "$PS1"'

    activation_tester(Bash)
