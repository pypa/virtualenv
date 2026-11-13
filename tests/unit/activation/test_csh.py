from __future__ import annotations

import os
import re
import sys
from argparse import Namespace
from shutil import which
from subprocess import check_output, run
from typing import TYPE_CHECKING, Final, Protocol

import pytest
from packaging.version import Version
from prompt_matrix import SHELLS, drawn_prompt, generate_script, run_prompt

from virtualenv.activation import CShellActivator
from virtualenv.info import IS_WIN
from virtualenv.run import cli_run

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

_TCSH: Final[str | None] = which("tcsh")


def _tcsh_has_issue_117() -> bool:
    exe = f"tcsh{'.exe' if sys.platform == 'win32' else ''}"
    return bool(which(exe)) and Version(
        check_output([exe, "--version"], text=True, encoding="utf-8").split(" ")[1]
    ) >= Version("6.24.14")


def _is_bsd_csh() -> bool:
    shell = which("bsd-csh") or which("csh")
    return shell is not None and run([shell, "-fc", "if ($?tcsh) exit 77"], check=False).returncode != 77


@pytest.mark.skipif(IS_WIN, reason="csh is not supported on Windows")
@pytest.mark.parametrize(
    "shell",
    [
        pytest.param(shell, id=shell, marks=pytest.mark.skipif(which(shell) is None, reason=f"{shell} is unavailable"))
        for shell in ("tcsh", "csh")
    ],
)
@pytest.mark.parametrize(
    "boundary",
    [pytest.param(value, id=f"U+{ord(value):04X}") for value in "\n\r\v\f\x1c\x1d\x1e\x85\u2028\u2029"],
)
def test_cshell_prompt_collapses_line_boundaries(
    csh_venv: _CshVenv,
    tmp_path: Path,
    shell: str,
    boundary: str,
) -> None:
    dest, content = csh_venv("ordinary", prompt=f"first{boundary}second")
    script: Final = tmp_path / "activate.csh"
    script.write_text(content, encoding="utf-8")
    result: Final = run(
        [shell, "-f"],
        input=f'set prompt = "> "\nsource {script}\nprintf "%s\\n" "$VIRTUAL_ENV:q" "$VIRTUAL_ENV_PROMPT:q" "$prompt:q"\n',
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
        check=True,
    )
    assert (result.stdout, result.stderr) == (f"{dest}\nfirst second\n(first second) > \n", "")


@pytest.mark.parametrize(
    ("tcl_lib", "tk_lib", "activate_lines"),
    [
        pytest.param(
            "/path/to/tcl",
            "/path/to/tk",
            ["setenv TCL_LIBRARY '/path/to/tcl'", "setenv TK_LIBRARY '/path/to/tk'"],
            id="present",
        ),
        pytest.param(None, None, ["setenv TCL_LIBRARY ''"], id="missing"),
    ],
)
def test_cshell_tkinter_generation(tmp_path, tcl_lib, tk_lib, activate_lines) -> None:
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
    activator = CShellActivator(Namespace(prompt=None))

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

    assert [line for line in activate_lines if line not in activate] == []


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


class _CshVenv(Protocol):
    def __call__(self, name: str, *, prompt: str | None = None) -> tuple[Path, str]: ...


@pytest.fixture
def csh_venv(tmp_path: Path, current_fastest: str) -> _CshVenv:
    def create(name: str, *, prompt: str | None = None) -> tuple[Path, str]:
        (dest := tmp_path / name / "venv").parent.mkdir(parents=True)
        return dest, _create_csh_venv(dest, current_fastest, prompt)

    return create


def _create_csh_venv(dest: Path, current_fastest: str, prompt: str | None = None) -> str:
    cmd = ["--without-pip", str(dest), "--creator", current_fastest, "--no-periodic-update", "--activators", "cshell"]
    if prompt is not None:
        cmd += ["--prompt", prompt]
    cli_run(cmd)
    return (dest / "bin" / "activate.csh").read_text(encoding="utf-8")


# the deactivate tests only source the script, so they share one environment
@pytest.fixture(scope="module")
def csh_plain_activate(tmp_path_factory: pytest.TempPathFactory, current_fastest: str) -> Path:
    _create_csh_venv(dest := tmp_path_factory.mktemp("plain") / "venv", current_fastest)
    return dest / "bin" / "activate.csh"


@pytest.mark.skipif(IS_WIN, reason="csh is not supported on Windows")
@pytest.mark.parametrize(
    ("prompt", "tcsh_escaped", "plain_escaped"),
    [
        pytest.param("plain", "plain", "plain", id="plain"),
        pytest.param("has!bang", "has'\\\\'\\!bang", "has'\\\\'\\!bang", id="bang"),
        pytest.param("has%pct", "has%%pct", "has%pct", id="percent"),
        pytest.param("has^caret", "has'\\\\^'caret", "has^caret", id="caret"),
        pytest.param("a!b%p c", "a'\\\\'\\!b%%p c", "a'\\\\'\\!b%p c", id="bang-and-percent"),
    ],
)
def test_cshell_escapes_prompt_expansion(
    csh_venv: _CshVenv, prompt: str, tcsh_escaped: str, plain_escaped: str
) -> None:
    _, content = csh_venv(prompt, prompt=prompt)

    # tcsh treats a bare % as the start of a prompt escape and needs it doubled; plain csh has no such escape, and
    # doubling it there would show two literal percent signs, so activate.csh picks the branch to use at runtime
    assert f"set _virtualenv_prompt_tcsh = '{tcsh_escaped}'\n" in content
    assert f"set _virtualenv_prompt_plain = '{plain_escaped}'\n" in content


@pytest.mark.skipif(IS_WIN, reason="csh is not supported on Windows")
@pytest.mark.skipif(_TCSH is None, reason="tcsh is not installed")
@pytest.mark.parametrize(
    "name",
    [
        pytest.param("plain", id="plain"),
        pytest.param("has!bang", id="bang"),
        pytest.param("has!!doublebang", id="double-bang"),
        pytest.param("has'quote!bang", id="quote-and-bang"),
        pytest.param("A__VIRTUAL_PROMPT_DISPLAY_TCSH__B", id="display-placeholder"),
    ],
)
def test_cshell_activates_path_with_special_characters(
    csh_venv: Callable[[str], tuple[Path, str]], tmp_path: Path, name: str
) -> None:
    dest, content = csh_venv(name)
    # source from an ASCII path so the driver's own quoting cannot stand in for the script's
    script = tmp_path / "activate.csh"
    script.write_text(content, encoding="utf-8")

    result = run(
        [_TCSH, "-c", f'source {script} && printf "%s" "$VIRTUAL_ENV"'],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=90,
        check=False,
    )

    assert result.stdout == str(dest), result.stderr


@pytest.mark.skipif(IS_WIN or _TCSH is None, reason="tcsh is required")
@pytest.mark.parametrize(
    "option", [pytest.param("", id="default"), pytest.param("set backslash_quote\n", id="backslash-quote")]
)
@pytest.mark.parametrize(
    "value",
    [
        pytest.param("a\\b", id="backslash"),
        pytest.param("a\\\\b\\", id="trailing-backslash"),
        pytest.param("it's mine", id="apostrophe"),
        pytest.param("a\\!b", id="history-character"),
    ],
)
def test_cshell_prompt_preserves_quoting_mode(csh_venv: _CshVenv, tmp_path: Path, value: str, option: str) -> None:
    dest, content = csh_venv("ordinary", prompt=value)
    script: Final = tmp_path / "activate.csh"
    script.write_text(content, encoding="utf-8")
    result: Final = run(
        [_TCSH, "-f"],
        input=f'{option}set prompt = "> "\nsource {script}\nprintf "%s\\n" "$VIRTUAL_ENV:q" "$VIRTUAL_ENV_PROMPT:q" "$prompt:q"\n',
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
        check=True,
    )
    display: Final = value.replace("\\", "\\\\").replace("!", "\\!")
    assert result.stdout == f"{dest}\n{value}\n({display}) > \n"


def _assert_prompt_drawn(csh_venv: _CshVenv, tmp_path: Path, prompt: str, env: dict[str, str]) -> None:
    _, content = csh_venv("plain", prompt=prompt)
    script = tmp_path / "activate.csh"
    script.write_text(content, encoding="utf-8")

    # only an interactive shell draws the prompt, which is where tcsh turns ^c into a control character
    result = run(
        [_TCSH, "-f", "-i"],
        input=f"source {script}\nexit\n".encode(),
        env=env,
        capture_output=True,
        timeout=30,
        check=True,
    )

    assert f"({prompt}) ".encode() in result.stdout + result.stderr


@pytest.mark.skipif(IS_WIN or _TCSH is None, reason="requires tcsh")
@pytest.mark.parametrize("prompt", [pytest.param("%", id="percent"), pytest.param("has^caret", id="caret")])
def test_cshell_renders_prompt_literally(csh_venv: _CshVenv, tmp_path: Path, prompt: str) -> None:
    _assert_prompt_drawn(csh_venv, tmp_path, prompt, os.environ.copy())


@pytest.fixture
def gbk_env() -> dict[str, str]:
    # a legacy double-byte locale reads the last UTF-8 byte of 中 and the ASCII byte after it as one character
    locales = check_output(["locale", "-a"], text=True, encoding="utf-8").splitlines()
    if (locale := next((i for i in locales if i.lower().replace("-", "").endswith(".gbk")), None)) is None:
        pytest.skip("no gbk locale is installed")
    return {**os.environ, "LC_ALL": locale}


@pytest.mark.skipif(IS_WIN or _TCSH is None, reason="requires tcsh")
@pytest.mark.parametrize(
    "prompt",
    [
        pytest.param("中^b", id="gbk-caret"),
        pytest.param("中!b", id="gbk-history"),
        pytest.param(r"中\^b", id="gbk-backslash-caret"),
        pytest.param(r"丁\!", id="gbk-backslash-history"),
    ],
)
def test_cshell_renders_prompt_literally_in_gbk(
    csh_venv: _CshVenv, tmp_path: Path, gbk_env: dict[str, str], prompt: str
) -> None:
    _assert_prompt_drawn(csh_venv, tmp_path, prompt, gbk_env)


@pytest.mark.skipif(IS_WIN, reason="csh is not supported on Windows")
@pytest.mark.skipif(_TCSH is None, reason="tcsh is not installed")
@pytest.mark.parametrize("original", [pytest.param("", id="empty"), pytest.param("/usr/bin:/bin", id="populated")])
def test_cshell_deactivate_restores_path(csh_plain_activate: Path, original: str) -> None:
    driver = f'setenv PATH "{original}"\nsource {csh_plain_activate}\ndeactivate\necho "PATH=<$PATH>"\n'

    result = run([_TCSH, "-f"], input=driver, capture_output=True, text=True, encoding="utf-8", timeout=90, check=False)

    assert result.stdout == f"PATH=<{original}>\n", result.stderr


@pytest.mark.skipif(IS_WIN, reason="csh is not supported on Windows")
@pytest.mark.skipif(_TCSH is None, reason="tcsh is not installed")
@pytest.mark.parametrize(
    ("original_env", "restored"),
    [
        pytest.param({}, "<unset>", id="unset"),
        pytest.param({"PYTHONHOME": ""}, "", id="empty"),
        pytest.param({"PYTHONHOME": "/some/pythonhome"}, "/some/pythonhome", id="path"),
        pytest.param({"PYTHONHOME": "a b"}, "a b", id="space"),
        pytest.param({"PYTHONHOME": r"a\b"}, r"a\b", id="backslash"),
        pytest.param({"PYTHONHOME": "a!b"}, "a!b", id="history-character"),
        pytest.param({"PYTHONHOME": 'a"b'}, 'a"b', id="quote"),
        pytest.param({"PYTHONHOME": "a$HOME"}, "a$HOME", id="dollar"),
        pytest.param({"PYTHONHOME": "a\nb"}, "a\nb", id="newline"),
    ],
)
def test_cshell_unsets_pythonhome(csh_plain_activate: Path, original_env: dict[str, str], restored: str) -> None:
    report = 'if ($?PYTHONHOME) then\n    printenv PYTHONHOME\nelse\n    echo "<unset>"\nendif\n'
    driver = f"source {csh_plain_activate}\n{report}deactivate\n{report}"

    result = run(
        [_TCSH, "-f"],
        input=driver,
        env={key: value for key, value in os.environ.items() if key != "PYTHONHOME"} | original_env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=90,
        check=False,
    )

    assert (result.returncode, result.stdout, result.stderr) == (0, f"<unset>\n{restored}\n", "")


@pytest.mark.skipif(IS_WIN or _TCSH is None, reason="requires tcsh")
def test_cshell_python_starts_with_pythonhome(csh_plain_activate: Path) -> None:
    result = run(
        [_TCSH, "-f"],
        input=f"source {csh_plain_activate}\npython -c 'import sys; print(sys.prefix)'\n",
        env={**os.environ, "PYTHONHOME": "/nonexistent-pythonhome"},
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=90,
        check=False,
    )

    assert (result.returncode, result.stdout, result.stderr) == (0, f"{csh_plain_activate.parent.parent}\n", "")


@pytest.mark.skipif(IS_WIN or _TCSH is None, reason="requires tcsh")
def test_cshell_reactivation_restores_pythonhome(csh_plain_activate: Path) -> None:
    result = run(
        [_TCSH, "-f"],
        input=f"source {csh_plain_activate}\nsource {csh_plain_activate}\ndeactivate\nprintenv PYTHONHOME\n",
        env={**os.environ, "PYTHONHOME": "/some/pythonhome"},
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=90,
        check=False,
    )

    assert (result.returncode, result.stdout, result.stderr) == (0, "/some/pythonhome\n", "")


@pytest.mark.skipif(IS_WIN, reason="csh is not supported on Windows")
@pytest.mark.skipif(_TCSH is None, reason="tcsh is not installed")
def test_cshell_deactivate_removes_aliases(csh_plain_activate: Path) -> None:
    driver = f'source {csh_plain_activate}\ndeactivate\nalias deactivate\nalias pydoc\necho "done"\n'

    result = run([_TCSH, "-f"], input=driver, capture_output=True, text=True, encoding="utf-8", timeout=90, check=False)

    assert result.stdout == "done\n", result.stderr


@pytest.mark.skipif(IS_WIN, reason="csh is not supported on Windows")
@pytest.mark.skipif(_TCSH is None, reason="tcsh is not installed")
def test_cshell_reactivation_restores_original_path(csh_plain_activate: Path) -> None:
    driver = (
        f'setenv PATH "/original/path"\nsource {csh_plain_activate}\nsource {csh_plain_activate}\ndeactivate\n'
        'echo "PATH=<$PATH>"\n'
    )

    result = run([_TCSH, "-f"], input=driver, capture_output=True, text=True, encoding="utf-8", timeout=90, check=False)

    assert result.stdout == "PATH=</original/path>\n", result.stderr


@pytest.mark.slow
@pytest.mark.skipif(_tcsh_has_issue_117(), reason="https://github.com/tcsh-org/tcsh/issues/117")
def test_csh(activation_tester_class, activation_tester) -> None:
    class Csh(activation_tester_class):
        def __init__(self, session) -> None:
            super().__init__(CShellActivator, session, "csh", "activate.csh", "csh")

        def activate_call(self, script: Path) -> str:
            return f"source {self.quote(str(script))}"

        def print_prompt(self) -> str:
            # Original csh doesn't print the last newline,
            # breaking the test; hence the trailing echo.
            return "echo 'source \"$VIRTUAL_ENV/bin/activate.csh\"; echo $prompt' | csh -i ; echo"

    activation_tester(Csh)


@pytest.mark.skipif(IS_WIN or which("csh") is None, reason="requires csh")
def test_cshell_disabled_prompt_preserves_existing_value(csh_venv: _CshVenv) -> None:
    dest, _ = csh_venv("plain", prompt="owner's prompt")
    result: Final = run(
        ["csh", "-f"],
        input=f"set prompt = original\nsetenv VIRTUAL_ENV_DISABLE_PROMPT 1\nsource {dest / 'bin' / 'activate.csh'}\necho $prompt\n",
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    assert result.stdout == "original\n"


@pytest.mark.skipif(IS_WIN or not _is_bsd_csh(), reason="requires bsd-csh")
def test_bsd_cshell_displays_one_backslash(csh_venv: _CshVenv) -> None:
    shell: Final = which("bsd-csh") or which("csh")
    dest, _ = csh_venv("plain", prompt="a\\b")
    result: Final = run(
        [shell, "-f", "-i"],
        input=f"source {dest / 'bin' / 'activate.csh'}\nexit\n",
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    assert "(a\\b) " in result.stdout + result.stderr


@pytest.mark.skipif(IS_WIN, reason="csh is not supported on Windows")
def test_cshell_skips_multiline_destination(tmp_path: Path) -> None:
    destination = tmp_path / "env\nname"
    scripts = destination / "bin"
    scripts.mkdir(parents=True)
    (scripts / "activate.csh").write_text("old", encoding="utf-8")
    session: Final = cli_run([str(destination), "--no-seed", "--activators", "cshell"])
    assert (list(scripts.glob("*.csh")), session.activators) == ([], [])


@pytest.mark.skipif(IS_WIN or _TCSH is None, reason="requires tcsh")
@pytest.mark.parametrize(
    "boundary",
    [
        pytest.param("\r", id="carriage-return"),
        pytest.param("\u2028", id="line-separator"),
        pytest.param("\x1c", id="file-separator"),
    ],
)
def test_cshell_preserves_non_newline_path(csh_venv: _CshVenv, tmp_path: Path, boundary: str) -> None:
    dest, _ = csh_venv(f"a{boundary}b")
    # copied as bytes, because text mode reads the carriage return in the path back as a newline
    script = tmp_path / "activate.csh"
    script.write_bytes((dest / "bin" / "activate.csh").read_bytes())

    result = run(
        [_TCSH, "-f"],
        input=f'source {script}\nprintf "%s" "$VIRTUAL_ENV:q"\n'.encode(),
        capture_output=True,
        timeout=30,
        check=True,
    )

    assert result.stdout == str(dest).encode()


_TEST_CSHELL_HISTCHARS_REPLACES_HASH_IN_PROMPT_PATTERN: Final[re.Pattern[str]] = re.compile(r"\(a%\d+b\) __END__")


@pytest.mark.skipif(IS_WIN or _TCSH is None, reason="requires tcsh")
@pytest.mark.parametrize("state", list(SHELLS["cshell"].states))
def test_cshell_histchars_replaces_hash_in_prompt(tmp_path: Path, state: str) -> None:
    result: Final = run_prompt(
        "cshell", generate_script("cshell", tmp_path / "env", "a%#b"), state, "histchars", tmp_path
    )

    assert _TEST_CSHELL_HISTCHARS_REPLACES_HASH_IN_PROMPT_PATTERN.fullmatch(drawn_prompt("cshell", result))
