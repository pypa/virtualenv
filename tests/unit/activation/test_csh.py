from __future__ import annotations

import sys
from argparse import Namespace
from shutil import which
from subprocess import check_output, run
from typing import TYPE_CHECKING

import pytest
from packaging.version import Version

from virtualenv.activation import CShellActivator
from virtualenv.info import IS_WIN
from virtualenv.run import cli_run

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

TCSH = which("tcsh")


@pytest.mark.parametrize(
    ("tcl_lib", "tk_lib", "present"),
    [
        ("/path/to/tcl", "/path/to/tk", True),
        (None, None, False),
    ],
)
def test_cshell_tkinter_generation(tmp_path, tcl_lib, tk_lib, present) -> None:
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
    activator = CShellActivator(options)

    # WHEN
    activator.generate(creator)
    content = (creator.bin_dir / "activate.csh").read_text(encoding="utf-8")

    # PKG_CONFIG_PATH is always set
    assert "test $?_OLD_PKG_CONFIG_PATH != 0" in content
    assert 'set _OLD_PKG_CONFIG_PATH="$PKG_CONFIG_PATH"' in content
    assert 'setenv PKG_CONFIG_PATH "${VIRTUAL_ENV}/lib/pkgconfig:${PKG_CONFIG_PATH}"' in content
    assert 'setenv PKG_CONFIG_PATH "${VIRTUAL_ENV}/lib/pkgconfig"' in content
    assert 'setenv PKG_CONFIG_PATH "$_OLD_PKG_CONFIG_PATH:q"' in content
    assert "unset _OLD_PKG_CONFIG_PATH" in content

    if present:
        assert "test $?_OLD_VIRTUAL_TCL_LIBRARY != 0" in content
        assert "test $?_OLD_VIRTUAL_TK_LIBRARY != 0" in content
        assert "setenv TCL_LIBRARY /path/to/tcl" in content
        assert "setenv TK_LIBRARY /path/to/tk" in content
    else:
        assert "setenv TCL_LIBRARY ''" in content


@pytest.fixture
def csh_venv(tmp_path: Path, current_fastest: str) -> Callable[[str], tuple[Path, str]]:
    def create(name: str) -> tuple[Path, str]:
        dest = tmp_path / name / "venv"
        dest.parent.mkdir(parents=True)
        cli_run([
            "--without-pip",
            str(dest),
            "--creator",
            current_fastest,
            "--no-periodic-update",
            "--activators",
            "cshell",
        ])
        return dest, (dest / "bin" / "activate.csh").read_text(encoding="utf-8")

    return create


@pytest.mark.skipif(IS_WIN, reason="csh is not supported on Windows")
def test_cshell_escapes_history_character(csh_venv: Callable[[str], tuple[Path, str]]) -> None:
    dest, content = csh_venv("has!bang")

    assert f"setenv VIRTUAL_ENV '{str(dest).replace('!', chr(92) + '!')}'\n" in content


@pytest.mark.skipif(IS_WIN, reason="csh is not supported on Windows")
@pytest.mark.skipif(TCSH is None, reason="tcsh is not installed")
@pytest.mark.parametrize(
    "name",
    [
        pytest.param("plain", id="plain"),
        pytest.param("has!bang", id="bang"),
        pytest.param("has!!doublebang", id="double-bang"),
        pytest.param("has'quote!bang", id="quote-and-bang"),
    ],
)
def test_cshell_activates_path_with_history_character(
    csh_venv: Callable[[str], tuple[Path, str]], tmp_path: Path, name: str
) -> None:
    dest, content = csh_venv(name)
    # source from an ASCII path so the driver's own quoting cannot stand in for the script's
    script = tmp_path / "activate.csh"
    script.write_text(content, encoding="utf-8")

    result = run(
        [TCSH, "-c", f'source {script} && printf "%s" "$VIRTUAL_ENV"'],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=90,
        check=False,
    )

    assert result.stdout == str(dest), result.stderr


@pytest.mark.slow
def test_csh(activation_tester_class, activation_tester) -> None:
    exe = f"tcsh{'.exe' if sys.platform == 'win32' else ''}"
    if which(exe):
        version_text = check_output([exe, "--version"], text=True, encoding="utf-8")
        version = Version(version_text.split(" ")[1])
        if version >= Version("6.24.14"):
            pytest.skip("https://github.com/tcsh-org/tcsh/issues/117")

    class Csh(activation_tester_class):
        def __init__(self, session) -> None:
            super().__init__(CShellActivator, session, "csh", "activate.csh", "csh")

        def print_prompt(self) -> str:
            # Original csh doesn't print the last newline,
            # breaking the test; hence the trailing echo.
            return "echo 'source \"$VIRTUAL_ENV/bin/activate.csh\"; echo $prompt' | csh -i ; echo"

    activation_tester(Csh)
