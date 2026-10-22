from __future__ import annotations

import shlex
import shutil
import subprocess
import sys
from argparse import Namespace
from pathlib import Path
from typing import TYPE_CHECKING, Final

import pytest
from prompt_matrix import generate_script

from virtualenv.activation import BashActivator
from virtualenv.info import IS_WIN
from virtualenv.run import cli_run

if TYPE_CHECKING:
    from collections.abc import Callable


_BASH: Final = shutil.which("bash")


@pytest.mark.skipif(_BASH is None or (IS_WIN and "\\git\\" not in _BASH.lower()), reason="requires native bash")
@pytest.mark.parametrize(
    ("setup", "expected"),
    [
        pytest.param("", "(example) base ", id="bash"),
        pytest.param("unset BASH_VERSION ZSH_VERSION;", "base ", id="unrecognized-shell"),
    ],
)
def test_prompt_requires_known_shell(tmp_path: Path, current_fastest: str, setup: str, expected: str) -> None:
    session: Final = cli_run([
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
    result: Final = subprocess.run(
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


@pytest.fixture
def moved_bash_activate(tmp_path: Path, current_fastest: str) -> Path:
    session: Final = cli_run([
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


@pytest.mark.skipif(IS_WIN, reason="requires POSIX shells")
@pytest.mark.parametrize(
    "failure",
    [
        pytest.param("shell", id="unsupported-shell"),
        pytest.param("tools", id="missing-tools"),
        pytest.param("config", id="missing-config"),
    ],
)
def test_bash_relocation_stops_when_unavailable(tmp_path: Path, moved_bash_activate: Path, failure: str) -> None:
    if failure == "config":
        (moved_bash_activate.parents[1] / "pyvenv.cfg").unlink()
    path: Final = str(tmp_path) if failure == "tools" else "/usr/bin:/bin"
    result: Final = subprocess.run(
        [
            _BASH,
            "-c",
            ("unset BASH_VERSION; " if failure == "shell" else "")
            + '. "$1"; printf "%s|%s|%s" "$?" "$PATH" "${VIRTUAL_ENV-unset}"',
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


@pytest.mark.skipif(not IS_WIN, reason="needs Git Bash and a Scripts directory")
def test_bash_relocation_resolves_under_git_bash(moved_bash_activate: Path) -> None:
    if (git := shutil.which("git")) is None or not (bash := Path(git).parents[1] / "bin" / "bash.exe").exists():
        pytest.skip("needs Git for Windows")
    result: Final = subprocess.run(
        [str(bash), "-c", 'source "$1" && cygpath -w "$VIRTUAL_ENV"', "bash", str(moved_bash_activate)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )

    assert (result.returncode, result.stdout.strip()) == (0, str(moved_bash_activate.parents[1]))


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

        def print_prompt(self) -> str:
            return (
                'if ((BASH_VERSINFO[0] * 100 + BASH_VERSINFO[1] >= 404)); then printf "%s\\n" "${PS1@P}"; '
                "else printf 'exit\\n' | PS1=\"$PS1\" bash --noprofile --norc -i 2>&1 >/dev/null; fi"
            )

    activation_tester(Bash)


@pytest.mark.skipif(IS_WIN, reason="requires POSIX shells")
@pytest.mark.parametrize("mode", [pytest.param("eval", id="eval"), pytest.param("stdin", id="stdin")])
def test_bash_relocation_without_source_preserves_path(moved_bash_activate: Path, mode: str) -> None:
    result: Final = subprocess.run(
        [
            _BASH,
            "--noprofile",
            "--norc",
            "-c",
            'eval "$(cat "$1")"; printf "%s|%s" "$PATH" "${VIRTUAL_ENV-unset}"',
            "test",
            str(moved_bash_activate),
        ]
        if mode == "eval"
        else [_BASH, "--noprofile", "--norc"],
        input=None
        if mode == "eval"
        else moved_bash_activate.read_text(encoding="utf-8") + '\nprintf "%s|%s" "$PATH" "${VIRTUAL_ENV-unset}"',
        env={"PATH": "/usr/bin:/bin"},
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    assert result.stdout == "/usr/bin:/bin|unset"


@pytest.mark.skipif(IS_WIN, reason="requires POSIX bash")
def test_bash_relocation_rejects_sourced_wrapper(moved_bash_activate: Path) -> None:
    wrapper: Final = moved_bash_activate.with_name("wrapper")
    wrapper.write_text('eval "$(cat "$1")"\n', encoding="utf-8")
    result: Final = subprocess.run(
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
    result: Final = subprocess.run(
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


@pytest.mark.skipif(IS_WIN, reason="requires POSIX bash")
@pytest.mark.parametrize(
    "child",
    [
        pytest.param(["bash", "--noprofile", "--norc", "-i"], id="child-bash"),
        pytest.param(["dash", "-i"], id="child-dash"),
    ],
)
def test_bash_child_shell_draws_inherited_prompt(tmp_path: Path, child: list[str]) -> None:
    if shutil.which(child[0]) is None:
        pytest.skip(f"{child[0]} is not installed")
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
    result: Final = subprocess.run(
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
