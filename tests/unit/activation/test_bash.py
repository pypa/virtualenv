from __future__ import annotations

import os
import shlex
import shutil
import subprocess
import sys
from argparse import Namespace
from pathlib import Path
from typing import TYPE_CHECKING, Final, NamedTuple

import pytest
from prompt_matrix import generate_script

from virtualenv.activation import BashActivator
from virtualenv.info import IS_CPYTHON, IS_WIN
from virtualenv.run import cli_run

if TYPE_CHECKING:
    from collections.abc import Callable

    from virtualenv.run.session import Session


_BASH: Final[str | None] = shutil.which("bash")
_GIT_BASH: Final[Path] = Path(os.environ.get("PROGRAMFILES", "")) / "Git/bin/bash.exe"


@pytest.mark.skipif(not IS_WIN or not _GIT_BASH.is_file(), reason="requires Git Bash on Windows")
def test_bash_activation_after_batch_keeps_path(tmp_path: Path) -> None:
    session = cli_run(["--no-seed", "--no-periodic-update", str(tmp_path / "env")])
    probe = tmp_path / "probe.sh"
    probe.write_text(
        "original=$PATH\n"
        '[[ "$_OLD_VIRTUAL_PATH" == *";"* ]] || exit 1\n'
        '. "$(cygpath -u "$1")" || exit 2\n'
        "command -v uname >/dev/null || exit 3\n"
        "command -v basename >/dev/null || exit 4\n"
        "deactivate\n"
        '[[ "$PATH" == "$original" ]] || exit 5\n',
        encoding="utf-8",
    )
    launcher = tmp_path / "launch.cmd"
    launcher.write_text(
        f'@echo off\ncall "{session.creator.bin_dir / "activate.bat"}"\n'
        f'"{_GIT_BASH}" --norc --noprofile "{probe}" "{session.creator.bin_dir / "activate"}"\n',
        encoding="utf-8",
    )
    result = subprocess.run(
        ["cmd", "/d", "/c", str(launcher)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
        check=False,
    )
    assert (result.returncode, result.stderr) == (0, "")


@pytest.mark.skipif(IS_WIN or _BASH is None, reason="requires POSIX bash")
def test_bash_activation_ignores_inherited_path_backup(tmp_path: Path) -> None:
    session = cli_run(["--no-seed", "--activators", "bash", str(tmp_path / "env")])
    result = subprocess.run(
        [
            _BASH,
            "--norc",
            "--noprofile",
            "-c",
            'original=$PATH; . "$1"; deactivate; [ "$PATH" = "$original" ]',
            "test",
            str(session.creator.bin_dir / "activate"),
        ],
        env={**os.environ, "_OLD_VIRTUAL_PATH": r"C:\Windows;C:\Tools"},
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
        check=False,
    )
    assert (result.returncode, result.stderr) == (0, "")


@pytest.mark.parametrize(
    ("shell", "source"),
    [
        pytest.param(
            "bash", '. "$1"', id="bash", marks=pytest.mark.skipif(IS_WIN or _BASH is None, reason="requires bash")
        ),
        pytest.param(
            "dash",
            '. "$1"',
            id="dash",
            marks=pytest.mark.skipif(IS_WIN or shutil.which("dash") is None, reason="requires dash"),
        ),
        pytest.param(
            _GIT_BASH,
            '. "$(cygpath -u "$1")"',
            id="git-bash",
            marks=pytest.mark.skipif(not IS_WIN or not _GIT_BASH.is_file(), reason="requires Git Bash"),
        ),
    ],
)
def test_bash_reactivation_restores_path(tmp_path: Path, shell: str | Path, source: str) -> None:
    session = cli_run(["--no-seed", "--activators", "bash", str(tmp_path / "env")])
    result = subprocess.run(
        [
            shell,
            "-c",
            f'original=$PATH; {source}; {source}; deactivate; [ "$PATH" = "$original" ]',
            "test",
            str(session.creator.bin_dir / "activate"),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
        check=False,
    )
    assert (result.returncode, result.stderr) == (0, "")


@pytest.fixture(params=[pytest.param("C", id="c"), pytest.param("utf8", id="utf8")])
def tcl_locale(request: pytest.FixtureRequest) -> str:
    if request.param == "C":
        return "C"
    locales = subprocess.check_output(["locale", "-a"], text=True, encoding="utf-8").splitlines()
    selected = next((name for name in locales if name.lower() in {"c.utf8", "en_us.utf8"}), None)
    if selected is None:
        pytest.skip("requires a UTF-8 locale")
    return selected


@pytest.mark.skipif(IS_WIN or not IS_CPYTHON or _BASH is None, reason="requires CPython's Tcl discovery and POSIX bash")
def test_bash_keeps_nonascii_tcl_library_bytes(tmp_path: Path, tcl_locale: str) -> None:
    tcl = pytest.importorskip("tkinter").Tcl()
    library = tmp_path / "andré" / Path(tcl.eval("info library")).name
    shutil.copytree(tcl.eval("info library"), library)
    env = {**os.environ, "HOME": str(tmp_path), "LC_ALL": tcl_locale, "TCL_LIBRARY": str(library)}
    env.pop("VIRTUAL_ENV", None)
    dest = tmp_path / "env"
    subprocess.run(
        [
            sys.executable,
            "-m",
            "virtualenv",
            "--no-periodic-update",
            "--no-seed",
            "--app-data",
            str(tmp_path / "cache"),
            str(dest),
        ],
        env=env,
        capture_output=True,
        timeout=60,
        check=True,
    )
    result = subprocess.run(
        [
            _BASH,
            "--norc",
            "--noprofile",
            "-c",
            '. "$1"; printf "%s\\n%s\\n" "$VIRTUAL_ENV" "$TCL_LIBRARY"; python -c "import sys, tkinter; tkinter.Tcl(); print(sys.prefix)"',
            "test",
            str(dest / "bin/activate"),
        ],
        env=env,
        capture_output=True,
        timeout=60,
        check=True,
    )
    assert (result.stdout.splitlines(), result.stderr) == (
        [os.fsencode(dest), os.fsencode(library), os.fsencode(dest)],
        b"",
    )


@pytest.mark.skipif(_BASH is None or (IS_WIN and "\\git\\" not in _BASH.lower()), reason="requires native bash")
@pytest.mark.parametrize("original", [pytest.param("", id="empty"), pytest.param("/some/pythonhome", id="path")])
def test_bash_clears_pythonhome(tmp_path: Path, original: str) -> None:
    session = cli_run(["--no-seed", "--activators", "bash", str(tmp_path / "env")])
    result = subprocess.run(
        [
            _BASH,
            "--norc",
            "--noprofile",
            "-c",
            (
                '. "$1"; printf "%s|%s\\n" "${PYTHONHOME+x}" "$PYTHONHOME"; deactivate; '
                'printf "%s|%s\\n" "${PYTHONHOME+x}" "$PYTHONHOME"'
            ),
            "test",
            str(session.creator.bin_dir / "activate"),
        ],
        env={**os.environ, "PYTHONHOME": original},
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
        check=False,
    )

    assert (result.returncode, result.stdout, result.stderr) == (0, f"|\nx|{original}\n", "")


@pytest.mark.skipif(_BASH is None or IS_WIN, reason="Git Bash rewrites the bin path with cygpath")
@pytest.mark.parametrize(
    ("original", "suffix"),
    [
        pytest.param("", "", id="empty"),
        pytest.param(":first", "::first", id="leading-empty-entry"),
        pytest.param("/usr/bin:/bin", ":/usr/bin:/bin", id="populated"),
    ],
)
def test_bash_prepends_bin_to_path(tmp_path: Path, original: str, suffix: str) -> None:
    session: Final[Session] = cli_run(["--no-seed", "--activators", "bash", str(tmp_path / "env")])
    result: Final[subprocess.CompletedProcess[str]] = subprocess.run(
        [
            _BASH,
            "--norc",
            "--noprofile",
            "-c",
            '. "$1"; printf "%s" "$PATH"',
            "test",
            str(session.creator.bin_dir / "activate"),
        ],
        env={**os.environ, "PATH": original},
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
        check=False,
    )

    # with PATH emptied, activate cannot find uname or basename, so only stdout is checked
    assert result.stdout == f"{session.creator.bin_dir}{suffix}"


@pytest.mark.skipif(_BASH is None or (IS_WIN and "\\git\\" not in _BASH.lower()), reason="requires native bash")
@pytest.mark.parametrize(
    ("setup", "expected"),
    [
        pytest.param("", "(example) base ", id="bash"),
        pytest.param("unset BASH_VERSION ZSH_VERSION;", "base ", id="unrecognized-shell"),
    ],
)
def test_prompt_requires_known_shell(tmp_path: Path, current_fastest: str, setup: str, expected: str) -> None:
    session: Final[Session] = cli_run([
        str(tmp_path / "env"),
        "--creator",
        current_fastest,
        "--without-pip",
        "--no-periodic-update",
        "--activators",
        "bash",
        "--prompt",
        "example",
    ])
    result: Final[subprocess.CompletedProcess[str]] = subprocess.run(
        [
            _BASH,
            "--norc",
            "--noprofile",
            "-c",
            f'{setup} PS1="base "; . "$1"; printf "%s|%s" "$PS1" "$VIRTUAL_ENV_PROMPT"',
            "test",
            str(session.creator.bin_dir / "activate"),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
        check=True,
    )
    assert result.stdout == f"{expected}|example"


@pytest.mark.skipif(_BASH is None or shutil.which("localedef") is None, reason="requires bash and localedef")
def test_bash_prompt_survives_gb18030_source(tmp_path: Path, gb18030_session: dict[str, str]) -> None:
    script = generate_script("bash", tmp_path / "env", "a你0")
    result = subprocess.run(
        [
            _BASH,
            "--norc",
            "--noprofile",
            "-c",
            '. "$1"; printf %s "$VIRTUAL_ENV_PROMPT"',
            "test",
            str(script),
        ],
        env=gb18030_session,
        capture_output=True,
        check=False,
    )

    assert (result.returncode, result.stdout, result.stderr) == (0, "a你0".encode(), b"")


@pytest.fixture
def gb18030_session(tmp_path: Path) -> dict[str, str]:
    locale_dir = tmp_path / "locales"
    locale_dir.mkdir()
    subprocess.run(
        [
            "localedef",
            "-c",
            "-f",
            str(Path(__file__).with_name("gb18030.charmap")),
            "-i",
            str(Path(__file__).with_name("zh_CN.locale")),
            str(locale_dir / "zh_CN.GB18030"),
        ],
        capture_output=True,
        check=False,
    )
    env = {**os.environ, "LC_ALL": "zh_CN.GB18030", "LOCPATH": str(locale_dir)}
    if subprocess.run(["locale", "charmap"], env=env, capture_output=True, check=False).stdout.strip() != b"GB18030":
        pytest.skip("glibc GB18030 locale is unavailable")
    return env


@pytest.mark.parametrize(
    "shell",
    [
        pytest.param("bash", marks=pytest.mark.skipif(_BASH is None, reason="bash is unavailable"), id="bash"),
        pytest.param(
            "dash", marks=pytest.mark.skipif(shutil.which("dash") is None, reason="dash is unavailable"), id="dash"
        ),
        pytest.param(
            "zsh", marks=pytest.mark.skipif(shutil.which("zsh") is None, reason="zsh is unavailable"), id="zsh"
        ),
    ],
)
@pytest.mark.skipif(IS_WIN, reason="Windows shell paths differ from the host paths")
def test_bash_prompt_unicode_survives_posix_shells(tmp_path: Path, shell: str) -> None:
    script = generate_script("bash", tmp_path / "env", "a你0")
    result = subprocess.run(
        [
            shell,
            "-c",
            '. "$1"; printf %s "$VIRTUAL_ENV_PROMPT"',
            shell,
            str(script),
        ],
        env={**os.environ, "LC_ALL": "C.UTF-8"},
        capture_output=True,
        check=False,
    )

    assert (result.returncode, result.stdout, result.stderr) == (0, "a你0".encode(), b"")


@pytest.mark.skipif(IS_WIN or _BASH is None, reason="requires POSIX bash")
def test_bash_prompt_unicode_survives_custom_ifs(tmp_path: Path) -> None:
    script = generate_script("bash", tmp_path / "env", "a你0")
    result = subprocess.run(
        [
            _BASH,
            "--norc",
            "--noprofile",
            "-c",
            'IFS=你; . "$1"; printf %s "$VIRTUAL_ENV_PROMPT"',
            "test",
            str(script),
        ],
        env={**os.environ, "LC_ALL": "C.UTF-8"},
        capture_output=True,
        check=False,
    )

    assert (result.returncode, result.stdout, result.stderr) == (0, "a你0".encode(), b"")


@pytest.mark.skipif(IS_WIN or _BASH is None, reason="requires POSIX bash")
def test_bash_prompt_unicode_ignores_printf_function(tmp_path: Path) -> None:
    script = generate_script("bash", tmp_path / "env", "a你0")
    result = subprocess.run(
        [
            _BASH,
            "--norc",
            "--noprofile",
            "-c",
            'printf() { builtin printf hijacked; }; . "$1"; builtin printf %s "$VIRTUAL_ENV_PROMPT"',
            "test",
            str(script),
        ],
        env={**os.environ, "LC_ALL": "C.UTF-8"},
        capture_output=True,
        check=False,
    )

    assert (result.returncode, result.stdout, result.stderr) == (0, "a你0".encode(), b"")


@pytest.mark.skipif(IS_WIN or shutil.which("zsh") is None, reason="requires POSIX zsh")
def test_bash_prompt_unicode_uses_zsh_builtin_printf(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            "zsh",
            "-f",
            "-c",
            'setopt ERR_EXIT; command() { return 127; }; . "$1"; print -rn -- "$VIRTUAL_ENV_PROMPT"',
            "zsh",
            str(generate_script("bash", tmp_path / "env", "a你0")),
        ],
        env={**os.environ, "LC_ALL": "C.UTF-8"},
        capture_output=True,
        check=False,
    )

    assert (result.returncode, result.stdout, result.stderr) == (0, "a你0".encode(), b"")


@pytest.mark.skipif(IS_WIN, reason="Github Actions ships with WSL bash")
@pytest.mark.parametrize(
    ("tcl_lib", "tk_lib", "expected_snippets"),
    [
        pytest.param(
            "/path/to/tcl",
            "/path/to/tk",
            [
                'if [ /path/to/tcl != "" ]; then',
                "TCL_LIBRARY=/path/to/tcl",
                "export TCL_LIBRARY",
                'if [ /path/to/tk != "" ]; then',
                "TK_LIBRARY=/path/to/tk",
                "export TK_LIBRARY",
            ],
            id="present",
        ),
        # When not present, the if condition is false, so the block is not executed
        pytest.param(
            None,
            None,
            ["if [ '' != \"\" ]; then", "TCL_LIBRARY=''", "export TCL_LIBRARY"],
            id="missing",
        ),
    ],
)
def test_bash_tkinter_generation(tmp_path, tcl_lib, tk_lib, expected_snippets: list[str]) -> None:
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
    activator = BashActivator(Namespace(prompt=None))

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

    missing: Final[list[str]] = [snippet for snippet in expected_snippets if snippet not in content]
    assert not missing, (missing, content)


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
def relocated_bash_venv(tmp_path: Path, current_fastest: str) -> Callable[[str], _Relocated]:
    def source_after_move(name: str) -> _Relocated:
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
        return _Relocated(result, relocated, work_dir)

    return source_after_move


class _Relocated(NamedTuple):
    result: subprocess.CompletedProcess[str]
    relocated: Path
    work_dir: Path


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


@pytest.fixture
def moved_bash_activate(tmp_path: Path, current_fastest: str) -> Path:
    session: Final[Session] = cli_run([
        "--without-pip",
        str(tmp_path / "original"),
        "--creator",
        current_fastest,
        "--no-periodic-update",
        "--activators",
        "bash",
    ])
    (tmp_path / "original").rename(tmp_path / "moved")
    return tmp_path / "moved" / session.creator.bin_dir.name / "activate"


@pytest.mark.skipif(IS_WIN or _BASH is None, reason="requires POSIX bash")
@pytest.mark.parametrize(
    ("prefix", "path_of", "prepare"),
    [
        pytest.param(
            "unset BASH_VERSION; ", lambda _tmp: "/usr/bin:/bin", lambda _activate: None, id="unsupported-shell"
        ),
        pytest.param("", str, lambda _activate: None, id="missing-tools"),
        pytest.param(
            "",
            lambda _tmp: "/usr/bin:/bin",
            lambda activate: (activate.parents[1] / "pyvenv.cfg").unlink(),
            id="missing-config",
        ),
    ],
)
def test_bash_relocation_stops_when_unavailable(
    tmp_path: Path,
    moved_bash_activate: Path,
    prefix: str,
    path_of: Callable[[Path], str],
    prepare: Callable[[Path], None],
) -> None:
    prepare(moved_bash_activate)
    path: Final[str] = path_of(tmp_path)
    result: Final[subprocess.CompletedProcess[str]] = subprocess.run(
        [
            _BASH,
            "-c",
            f'{prefix}. "$1"; printf "%s|%s|%s" "$?" "$PATH" "${{VIRTUAL_ENV-unset}}"',
            "activate",
            str(moved_bash_activate),
        ],
        env={"PATH": path},
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    assert result.stdout == f"1|{path}|unset"


@pytest.mark.skipif(IS_WIN or _BASH is None, reason="requires POSIX bash")
@pytest.mark.parametrize(
    ("name", "expected_output", "error"),
    [
        pytest.param("moved%func", "1|/usr/bin:/bin|unset", "shell PATH option", id="option"),
        pytest.param("moved:split", "1|/usr/bin:/bin|unset", "PATH separator", id="separator"),
        pytest.param("moved%20", "0|{env}/bin:/usr/bin:/bin|{env}", "does not exist!", id="literal-percent"),
    ],
)
def test_bash_relocation_handles_shell_path_option(
    tmp_path: Path, moved_bash_activate: Path, name: str, expected_output: str, error: str
) -> None:
    relocated: Final[Path] = tmp_path / name
    moved_bash_activate.parents[1].rename(relocated)
    result: Final[subprocess.CompletedProcess[str]] = subprocess.run(
        [
            _BASH,
            "-c",
            '. "$1"; printf "%s|%s|%s" "$?" "$PATH" "${VIRTUAL_ENV-unset}"',
            "activate",
            str(relocated / "bin" / "activate"),
        ],
        env={"PATH": "/usr/bin:/bin"},
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    assert result.stdout == expected_output.format(env=relocated)
    assert error in result.stderr


@pytest.fixture
def git_bash() -> Path:
    if (git := shutil.which("git")) is None or not (bash := Path(git).parents[1] / "bin" / "bash.exe").exists():
        pytest.skip("needs Git for Windows")
    return bash


@pytest.mark.skipif(not IS_WIN, reason="needs Git Bash and a Scripts directory")
def test_bash_relocation_resolves_under_git_bash(git_bash: Path, moved_bash_activate: Path) -> None:
    result: Final[subprocess.CompletedProcess[str]] = subprocess.run(
        [str(git_bash), "-c", 'source "$1" && cygpath -w "$VIRTUAL_ENV"', "bash", str(moved_bash_activate)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )

    assert (result.returncode, result.stdout.strip()) == (0, str(moved_bash_activate.parents[1])), result.stderr


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


@pytest.fixture(params=["bash", "zsh"])
def prompt_after_activate(
    request: pytest.FixtureRequest, tmp_path: Path, current_fastest: str
) -> Callable[[str | None, str], tuple[Path, str]]:
    if shutil.which(shell := request.param) is None:
        pytest.skip(f"{shell} is not installed")
    if shell == "bash":
        version: Final[str] = subprocess.run(
            ["bash", "-c", 'printf "%s" "$((BASH_VERSINFO[0] * 100 + BASH_VERSINFO[1]))"'],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        if int(version) < 404:
            pytest.skip("${PS1@P} needs bash 4.4 or later")

    def build(prompt: str | None, env_name: str) -> tuple[Path, str]:
        dest: Final[Path] = tmp_path / env_name
        args = [
            "--without-pip",
            str(dest),
            "--creator",
            current_fastest,
            "--no-periodic-update",
            "--activators",
            "bash",
        ]
        if prompt is not None:
            args += ["--prompt", prompt]
        cli_run(args)
        work_dir: Final[Path] = tmp_path / "workdir"
        work_dir.mkdir(exist_ok=True)
        # the path is passed as $1 so the outer shell cannot expand a payload dir name while locating the script;
        # ${PS1@P} renders the prompt exactly as bash does before each interactive command, and in zsh (e) applies
        # what PROMPT_SUBST does at each draw before (%) expands the prompt escapes
        render: Final[list[str]] = {
            "bash": ["bash", "--norc", "--noprofile", "-c", 'source "$1"; printf "%s" "${PS1@P}"'],
            "zsh": ["zsh", "-f", "-c", 'setopt prompt_subst; source "$1"; print -rn -- "${(%)${(e)PS1}}"'],
        }[shell]
        result: Final[subprocess.CompletedProcess[str]] = subprocess.run(
            [*render, shell, str(dest / "bin" / "activate")],
            capture_output=True,
            text=True,
            cwd=str(work_dir),
            encoding="utf-8",
            check=False,
        )
        return work_dir, result.stdout

    return build


@pytest.mark.skipif(IS_WIN, reason="Github Actions ships with WSL bash")
@pytest.mark.parametrize(
    "env_name",
    [
        pytest.param("x$(touch PWNED)y", id="dirname-command-substitution"),
        pytest.param("A__VIRTUAL_NAME__B/x'$(touch PWNED)'y", id="placeholder-in-parent-dir"),
    ],
)
def test_prompt_dirname_does_not_run_commands(
    prompt_after_activate: Callable[[str | None, str], tuple[Path, str]], env_name: str
) -> None:
    work_dir, _ = prompt_after_activate(None, env_name)

    assert not (work_dir / "PWNED").exists()


@pytest.mark.skipif(IS_WIN or shutil.which("dash") is None, reason="needs dash as a POSIX shell")
def test_bash_activate_sources_under_dash(tmp_path: Path, current_fastest: str) -> None:
    dest = tmp_path / "env"
    cli_run([
        "--without-pip",
        str(dest),
        "--creator",
        current_fastest,
        "--no-periodic-update",
        "--activators",
        "bash",
        "--prompt",
        "x$y",
    ])

    result = subprocess.run(
        [
            "dash",
            "-c",
            'PS1="base "; . "$1" && printf "%s|%s" "$VIRTUAL_ENV" "$PS1"',
            "dash",
            str(dest / "bin" / "activate"),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )

    assert (result.returncode, result.stdout) == (0, f"{dest}|base ")


@pytest.mark.skipif(IS_WIN, reason="Github Actions ships with WSL bash")
@pytest.mark.parametrize(
    "shell",
    [
        pytest.param(
            ["bash", "--norc", "--noprofile", "-O", "expand_aliases", "-c"],
            id="bash",
            marks=pytest.mark.skipif(_BASH is None, reason="bash is not installed"),
        ),
        pytest.param(
            ["zsh", "-f", "-c"],
            id="zsh",
            marks=pytest.mark.skipif(shutil.which("zsh") is None, reason="zsh is not installed"),
        ),
    ],
)
def test_bash_activate_with_pydoc_alias(tmp_path: Path, current_fastest: str, shell: list[str]) -> None:
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

    # the alias is defined on its own line, so it is in effect when the shell parses the sourced script
    result = subprocess.run(
        [
            *shell,
            'alias pydoc="python3 -m pydoc"\nsource "$1" && printf "%s" "$VIRTUAL_ENV"',
            shell[0],
            str(dest / "bin" / "activate"),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )

    assert (result.returncode, result.stdout, result.stderr) == (0, str(dest), "")


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
            return f"{super().activate_call(script)} || exit 1"

        def print_prompt(self) -> str:
            return (
                'if ((BASH_VERSINFO[0] * 100 + BASH_VERSINFO[1] >= 404)); then printf "%s\\n" "${PS1@P}"; '
                "else printf 'exit\\n' | PS1=\"$PS1\" bash --noprofile --norc -i 2>&1 >/dev/null; fi"
            )

    activation_tester(Bash)


@pytest.mark.skipif(IS_WIN or _BASH is None, reason="requires POSIX bash")
def test_bash_relocation_eval_without_source_preserves_path(moved_bash_activate: Path) -> None:
    result: Final[subprocess.CompletedProcess[str]] = subprocess.run(
        [
            _BASH,
            "--noprofile",
            "--norc",
            "-c",
            'eval "$(cat "$1")"; printf "%s|%s" "$PATH" "${VIRTUAL_ENV-unset}"',
            "test",
            str(moved_bash_activate),
        ],
        env={"PATH": "/usr/bin:/bin"},
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    assert result.stdout == "/usr/bin:/bin|unset"


@pytest.mark.skipif(IS_WIN or _BASH is None, reason="requires POSIX bash")
def test_bash_relocation_stdin_without_source_preserves_path(moved_bash_activate: Path) -> None:
    result: Final[subprocess.CompletedProcess[str]] = subprocess.run(
        [_BASH, "--noprofile", "--norc"],
        input=f'{moved_bash_activate.read_text(encoding="utf-8")}\nprintf "%s|%s" "$PATH" "${{VIRTUAL_ENV-unset}}"',
        env={"PATH": "/usr/bin:/bin"},
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    assert result.stdout == "/usr/bin:/bin|unset"


@pytest.mark.skipif(IS_WIN, reason="requires POSIX bash")
def test_bash_relocation_rejects_sourced_wrapper(moved_bash_activate: Path) -> None:
    wrapper: Final[Path] = moved_bash_activate.with_name("wrapper")
    wrapper.write_text('eval "$(cat "$1")"\n', encoding="utf-8")
    result: Final[subprocess.CompletedProcess[str]] = subprocess.run(
        [
            "bash",
            "-c",
            '. "$1" "$2"; printf "%s|%s" "$PATH" "${VIRTUAL_ENV-unset}"',
            "test",
            str(wrapper),
            str(moved_bash_activate),
        ],
        env={"PATH": "/usr/bin:/bin"},
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    assert result.stdout == "/usr/bin:/bin|unset"


@pytest.mark.skipif(IS_WIN, reason="requires POSIX bash")
@pytest.mark.parametrize("setup", [pytest.param("", id="default"), pytest.param("BASH_COMPAT=42; ", id="compat42")])
def test_bash_prompt_stored_form(tmp_path: Path, setup: str) -> None:
    result: Final[subprocess.CompletedProcess[str]] = subprocess.run(
        [
            "bash",
            "--norc",
            "--noprofile",
            "-c",
            f'{setup}PS1=__END__; . "$1"; printf "%s" "$PS1"',
            "test",
            str(generate_script("bash", tmp_path / "env", "a\\b$c`d")),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )

    assert result.stdout == "(a\\\\\\\\b\\$c\\`d) __END__"


@pytest.mark.skipif(IS_WIN or _BASH is None, reason="requires POSIX bash")
def test_bash_prompt_ignores_printf_function(tmp_path: Path) -> None:
    script = generate_script("bash", tmp_path / "env", "normal")
    result = subprocess.run(
        [
            _BASH,
            "--norc",
            "--noprofile",
            "-c",
            'PS1=__END__; printf() { builtin printf hijacked; }; . "$1"; builtin printf %s "$PS1"',
            "test",
            str(script),
        ],
        capture_output=True,
        check=False,
    )

    assert (result.returncode, result.stdout, result.stderr) == (0, b"(normal) __END__", b"")


@pytest.mark.skipif(IS_WIN or _BASH is None, reason="requires POSIX bash")
@pytest.mark.parametrize(
    "setup",
    [
        pytest.param("set -o posix", id="posix"),
        pytest.param("shopt -u extquote", id="extquote-off"),
        pytest.param("readonly LC_ALL=C", id="readonly"),
        pytest.param("{ LC_ALL=virtualenv_missing_locale; } 2>/dev/null", id="missing-locale"),
        pytest.param("unset LC_ALL", id="unset"),
    ],
)
def test_bash_prompt_preserves_locale(tmp_path: Path, setup: str) -> None:
    result = subprocess.run(
        [
            "/bin/bash" if sys.platform == "darwin" else _BASH,
            "--norc",
            "--noprofile",
            "-ec",
            (
                f'{setup}; saved=${{LC_ALL-unset}}; . "$1"; '
                'test "${LC_ALL-unset}" = "$saved"; builtin printf %s "$PS1"'
            ),
            "test",
            str(generate_script("bash", tmp_path / "env", "é$5")),
        ],
        env={**os.environ, "LC_ALL": "C"},
        capture_output=True,
        check=True,
    )

    assert (result.stdout, result.stderr) == (b"(\xc3\xa9\001\002\\$5) ", b"")


@pytest.mark.skipif(IS_WIN or _BASH is None, reason="requires POSIX bash")
@pytest.mark.usefixtures("bash_prompt_rendering")
@pytest.mark.parametrize(
    ("source_locale", "draw_locale"),
    [
        pytest.param("C.UTF-8", "C.UTF-8", id="utf8"),
        pytest.param("zh_CN.gbk", "zh_CN.gbk", id="gbk"),
        pytest.param("zh_CN.gb18030", "zh_CN.gb18030", id="gb18030"),
        pytest.param("C.UTF-8", "zh_CN.gbk", id="utf8-to-gbk"),
        pytest.param("C.UTF-8", "zh_CN.gb18030", id="utf8-to-gb18030"),
        pytest.param("zh_CN.gbk", "C.UTF-8", id="gbk-to-utf8"),
    ],
)
@pytest.mark.parametrize(
    "prompt",
    [
        pytest.param("中$(printf X)", id="dollar"),
        pytest.param("中`printf X`", id="backtick"),
        pytest.param(r"中\more", id="backslash"),
    ],
)
def test_bash_prompt_escaping_across_locales(tmp_path: Path, source_locale: str, draw_locale: str, prompt: str) -> None:
    result = subprocess.run(
        [
            _BASH,
            "--norc",
            "--noprofile",
            "-c",
            '. "$1"; LC_ALL=$2; printf %s "${PS1@P}"',
            "test",
            str(generate_script("bash", tmp_path / "env", prompt)),
            draw_locale,
        ],
        env=_locale_env(source_locale, draw_locale),
        capture_output=True,
        check=False,
    )

    assert (result.returncode, result.stdout.replace(b"\001\002", b""), result.stderr) == (
        0,
        f"({prompt}) ".encode(),
        b"",
    )


def _locale_env(*locales: str) -> dict[str, str]:
    for locale in locales:
        env = {**os.environ, "LC_ALL": locale}
        if subprocess.run(
            [sys.executable, "-c", "import locale; locale.setlocale(locale.LC_CTYPE, '')"],
            env=env,
            capture_output=True,
            check=False,
        ).returncode:
            pytest.skip(f"{locale} is unavailable")
    return {**os.environ, "LC_ALL": locales[0]}


@pytest.fixture(scope="module")
def bash_prompt_rendering() -> None:
    version = subprocess.run(
        [_BASH, "-c", 'printf %s "$((BASH_VERSINFO[0] * 100 + BASH_VERSINFO[1]))"'],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    ).stdout
    if int(version) < 404:
        pytest.skip("${PS1@P} needs bash 4.4 or later")


@pytest.mark.skipif(IS_WIN or _BASH is None, reason="requires POSIX bash")
@pytest.mark.parametrize("locale", ["C.UTF-8", "zh_CN.gbk", "zh_CN.gb18030"])
def test_bash_long_prompt_activates_promptly(tmp_path: Path, locale: str) -> None:
    result = subprocess.run(
        [
            _BASH,
            "--norc",
            "--noprofile",
            "-c",
            '. "$1"; printf %s "$PS1"',
            "test",
            str(generate_script("bash", tmp_path / "env", "a" * 4000)),
        ],
        env=_locale_env(locale),
        capture_output=True,
        timeout=5,
        check=True,
    )

    assert result.stdout == b"(" + b"a" * 4000 + b") "


@pytest.mark.skipif(IS_WIN, reason="requires POSIX bash")
@pytest.mark.parametrize(
    "child",
    [
        pytest.param(
            ["bash", "--noprofile", "--norc", "-i"],
            id="child-bash",
            marks=pytest.mark.skipif(shutil.which("bash") is None, reason="bash is not installed"),
        ),
        pytest.param(
            ["dash", "-i"],
            id="child-dash",
            marks=pytest.mark.skipif(shutil.which("dash") is None, reason="dash is not installed"),
        ),
    ],
)
def test_bash_child_shell_draws_inherited_prompt(tmp_path: Path, child: list[str]) -> None:
    subprocess.run(
        ["bash", "--norc", "--noprofile", "-c", f"export PS1='$(touch CANARY)'; {shlex.join(child)} <<<exit"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )

    assert (tmp_path / "CANARY").exists()


@pytest.mark.skipif(IS_WIN or shutil.which("zsh") is None, reason="requires zsh")
def test_zsh_deactivate_restores_psvar(tmp_path: Path) -> None:
    result: Final[subprocess.CompletedProcess[str]] = subprocess.run(
        [
            "zsh",
            "-f",
            "-c",
            'psvar=(a b); . "$1"; print -r -- "$psvar[9]"; deactivate; print -r -- "${(j:,:)psvar}"',
            "zsh",
            str(generate_script("zsh", tmp_path / "env", "plain")),
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )

    assert result.stdout == "plain\na,b,,,,,,,\n"
