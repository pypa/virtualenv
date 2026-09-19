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
    activate = (creator.bin_dir / "activate.csh").read_text(encoding="utf-8")
    deactivate = (creator.bin_dir / "deactivate.csh").read_text(encoding="utf-8")

    # the restore side carries no per-venv placeholders, so it is identical regardless of `present`
    assert "if ($?_OLD_PKG_CONFIG_PATH) then" in deactivate
    assert 'setenv PKG_CONFIG_PATH "$_OLD_PKG_CONFIG_PATH:q"' in deactivate
    assert "unset _OLD_PKG_CONFIG_PATH" in deactivate
    assert "if ($?_OLD_VIRTUAL_TCL_LIBRARY) then" in deactivate
    assert "if ($?_OLD_VIRTUAL_TK_LIBRARY) then" in deactivate

    # PKG_CONFIG_PATH is always saved on activation
    assert 'set _OLD_PKG_CONFIG_PATH="$PKG_CONFIG_PATH"' in activate
    assert 'setenv PKG_CONFIG_PATH "${VIRTUAL_ENV}/lib/pkgconfig:${PKG_CONFIG_PATH}"' in activate
    assert 'setenv PKG_CONFIG_PATH "${VIRTUAL_ENV}/lib/pkgconfig"' in activate

    if present:
        assert "setenv TCL_LIBRARY /path/to/tcl" in activate
        assert "setenv TK_LIBRARY /path/to/tk" in activate
    else:
        assert "setenv TCL_LIBRARY ''" in activate


def test_cshell_generates_deactivate_script(tmp_path) -> None:
    class MockCreator:
        def __init__(self, dest) -> None:
            self.dest = dest
            self.bin_dir = dest / "bin"
            self.bin_dir.mkdir()
            self.interpreter = type("MockInterpreter", (), {"tcl_lib": None, "tk_lib": None})()
            self.pyenv_cfg = {}
            self.env_name = "my-env"

    creator = MockCreator(tmp_path)
    CShellActivator(Namespace(prompt=None)).generate(creator)

    assert (creator.bin_dir / "deactivate.csh").exists()
    assert "deactivate.csh" in (creator.bin_dir / "activate.csh").read_text(encoding="utf-8")


@pytest.fixture
def csh_venv(tmp_path: Path, current_fastest: str) -> Callable[..., tuple[Path, str]]:
    def create(name: str, *, prompt: str | None = None) -> tuple[Path, str]:
        dest = tmp_path / name / "venv"
        dest.parent.mkdir(parents=True)
        cmd = [
            "--without-pip",
            str(dest),
            "--creator",
            current_fastest,
            "--no-periodic-update",
            "--activators",
            "cshell",
        ]
        if prompt is not None:
            cmd += ["--prompt", prompt]
        cli_run(cmd)
        return dest, (dest / "bin" / "activate.csh").read_text(encoding="utf-8")

    return create


@pytest.mark.skipif(IS_WIN, reason="csh is not supported on Windows")
def test_cshell_escapes_history_character(csh_venv: Callable[..., tuple[Path, str]]) -> None:
    dest, content = csh_venv("has!bang")

    assert f"setenv VIRTUAL_ENV '{str(dest).replace('!', chr(92) + '!')}'\n" in content


@pytest.mark.skipif(IS_WIN, reason="csh is not supported on Windows")
@pytest.mark.parametrize(
    ("prompt", "tcsh_escaped", "plain_escaped"),
    [
        pytest.param("plain", "plain", "plain", id="plain"),
        pytest.param("has!bang", "has\\\\!bang", "has\\\\!bang", id="bang"),
        pytest.param("has%pct", "has%%pct", "has%pct", id="percent"),
        pytest.param("a!b%p c", "a\\\\!b%%p c", "a\\\\!b%p c", id="bang-and-percent"),
    ],
)
def test_cshell_escapes_prompt_expansion(
    csh_venv: Callable[..., tuple[Path, str]], prompt: str, tcsh_escaped: str, plain_escaped: str
) -> None:
    _, content = csh_venv(prompt, prompt=prompt)

    # tcsh treats a bare % as the start of a prompt escape and needs it doubled; plain csh has no such escape, and
    # doubling it there would show two literal percent signs, so activate.csh picks the branch to use at runtime
    assert f"set prompt = '(''{tcsh_escaped}'') '" in content
    assert f"set prompt = '(''{plain_escaped}'') '" in content


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


@pytest.mark.skipif(IS_WIN, reason="csh is not supported on Windows")
@pytest.mark.skipif(TCSH is None, reason="tcsh is not installed")
@pytest.mark.parametrize("original", [pytest.param("", id="empty"), pytest.param("/usr/bin:/bin", id="populated")])
def test_cshell_deactivate_restores_path(csh_venv: Callable[[str], tuple[Path, str]], original: str) -> None:
    dest, _ = csh_venv("plain")
    driver = f'setenv PATH "{original}"\nsource {dest / "bin" / "activate.csh"}\ndeactivate\necho "PATH=<$PATH>"\n'

    result = run([TCSH, "-f"], input=driver, capture_output=True, text=True, encoding="utf-8", timeout=90, check=False)

    assert result.stdout == f"PATH=<{original}>\n", result.stderr


@pytest.mark.skipif(IS_WIN, reason="csh is not supported on Windows")
@pytest.mark.skipif(TCSH is None, reason="tcsh is not installed")
def test_cshell_deactivate_removes_aliases(csh_venv: Callable[[str], tuple[Path, str]]) -> None:
    dest, _ = csh_venv("plain")
    driver = f'source {dest / "bin" / "activate.csh"}\ndeactivate\nalias deactivate\nalias pydoc\necho "done"\n'

    result = run([TCSH, "-f"], input=driver, capture_output=True, text=True, encoding="utf-8", timeout=90, check=False)

    assert result.stdout == "done\n", result.stderr


@pytest.mark.skipif(IS_WIN, reason="csh is not supported on Windows")
@pytest.mark.skipif(TCSH is None, reason="tcsh is not installed")
def test_cshell_reactivation_restores_original_path(csh_venv: Callable[[str], tuple[Path, str]]) -> None:
    dest, _ = csh_venv("plain")
    script = dest / "bin" / "activate.csh"
    driver = f'setenv PATH "/original/path"\nsource {script}\nsource {script}\ndeactivate\necho "PATH=<$PATH>"\n'

    result = run([TCSH, "-f"], input=driver, capture_output=True, text=True, encoding="utf-8", timeout=90, check=False)

    assert result.stdout == "PATH=</original/path>\n", result.stderr


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
