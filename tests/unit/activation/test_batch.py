from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
from argparse import Namespace
from typing import TYPE_CHECKING, Final

import pytest

from virtualenv import cli_run, session_via_cli
from virtualenv.activation import BatchActivator
from virtualenv.config.cli.parser import VirtualEnvOptions
from virtualenv.info import IS_WIN

if TYPE_CHECKING:
    from pathlib import Path

    from virtualenv.create.creator import Creator


@pytest.mark.skipif(not IS_WIN, reason="batch activation requires Windows")
def test_batch_clears_pythonhome(tmp_path: Path) -> None:
    creator = session_via_cli([str(tmp_path / "env"), "--no-seed"], setup_logging=False).creator
    creator.bin_dir.mkdir(parents=True)
    BatchActivator(VirtualEnvOptions(prompt=None)).generate(creator)
    driver = creator.bin_dir / "pythonhome.bat"
    driver.write_text(
        "@echo off\n@call activate.bat\n@if defined PYTHONHOME (echo set) else (echo unset)\n"
        "@call deactivate.bat\n@echo %PYTHONHOME%\n",
        encoding="utf-8",
    )
    inherited = str(tmp_path / "missing-pythonhome")
    result = subprocess.run(
        [os.environ["COMSPEC"], "/D", "/C", driver.name],
        cwd=creator.bin_dir,
        env={**os.environ, "PYTHONHOME": inherited},
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
        check=False,
    )

    assert (result.returncode, result.stdout.splitlines(), result.stderr) == (0, ["unset", inherited], "")


@pytest.fixture(scope="session")
def special_char_name():
    # Exclude ampersands, which batch activation does not support in paths.
    base = "'\";e-$ èрт🚒♞中片-j"
    if IS_WIN:
        base = base.replace('"', "").replace(";", "")
    encoding = "ascii" if IS_WIN else sys.getfilesystemencoding()
    result = ""
    for char in base:
        try:
            if char == char.encode(encoding, errors="strict").decode(encoding):
                result += char
        # a ValueError marks a character the encoding cannot round-trip
        except ValueError:  # ruff:ignore[try-except-in-loop]
            continue
    assert result
    return result


def test_batch_pydoc_bat_quoting(tmp_path: Path) -> None:
    creator = session_via_cli([str(tmp_path / "env"), "--no-seed"], setup_logging=False).creator
    creator.bin_dir.mkdir(parents=True)
    BatchActivator(VirtualEnvOptions(prompt=None)).generate(creator)

    assert '"%_PYDOC_BIN%python.exe" -m pydoc %*' in (creator.bin_dir / "pydoc.bat").read_text(encoding="utf-8")


@pytest.mark.skipif(not IS_WIN, reason="requires cmd.exe")
@pytest.mark.parametrize(
    ("pydoc_call", "path_prefix"),
    [
        pytest.param('call "{pydoc}" pydoc_probe', "", id="full-path"),
        pytest.param("call pydoc pydoc_probe", "{script_dir}{sep}", id="call-name"),
        pytest.param('call "pydoc" pydoc_probe', "{script_dir}{sep}", id="call-quoted-name"),
        pytest.param('call "pydoc.bat" pydoc_probe', "{script_dir}{sep}", id="call-quoted-file"),
        pytest.param('"pydoc" pydoc_probe', "{script_dir}{sep}", id="quoted-name"),
        pytest.param('"pydoc.bat" pydoc_probe', "{script_dir}{sep}", id="quoted-file"),
    ],
)
def test_batch_pydoc_uses_environment_python(tmp_path: Path, pydoc_call: str, path_prefix: str) -> None:
    creator = cli_run([str(tmp_path / "env space"), "--no-seed"], setup_logging=False).creator
    (tmp_path / "pydoc_probe.py").write_text("import sys\nprint(f'INTERPRETER={sys.executable}')\n", encoding="utf-8")
    (tmp_path / "pydoc_driver.bat").write_text(
        f"@echo off\n@{pydoc_call.format(pydoc=creator.bin_dir / 'pydoc.bat')}\n", encoding="utf-8"
    )
    result = subprocess.run(
        [os.environ["COMSPEC"], "/D", "/C", "pydoc_driver.bat"],
        cwd=tmp_path,
        env={
            **os.environ,
            "PATH": (
                f"{path_prefix.format(script_dir=creator.bin_dir, sep=os.pathsep)}"
                f"{os.path.dirname(sys.executable)}{os.pathsep}{os.environ['PATH']}"
            ),
        },
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert f"INTERPRETER={creator.bin_dir / 'python.exe'}" in result.stdout.splitlines()


@pytest.mark.skipif(not IS_WIN, reason="requires cmd.exe")
@pytest.mark.parametrize("pydoc_call", [pytest.param("pydoc", id="path"), pytest.param('"!launcher!"', id="full-path")])
def test_batch_pydoc_moved_env_with_exclamation_mark(tmp_path: Path, pydoc_call: str) -> None:
    created = cli_run([str(tmp_path / "env"), "--no-seed"], setup_logging=False).creator
    bin_dir = created.dest.rename(tmp_path / "env !q!") / created.bin_dir.name
    (tmp_path / "pydoc_probe.py").write_text("import sys\nprint(f'INTERPRETER={sys.executable}')\n", encoding="utf-8")
    result = subprocess.run(
        f'"{os.environ["COMSPEC"]}" /D /V:ON /S /C "{pydoc_call} pydoc_probe"',
        cwd=tmp_path,
        env={
            **os.environ,
            "q": "X",
            "launcher": str(bin_dir / "pydoc.bat"),
            "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
        },
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert f"INTERPRETER={bin_dir / 'python.exe'}" in result.stdout.splitlines()


@pytest.mark.parametrize(
    ("tcl_lib", "tk_lib", "activate_lines", "deactivate_lines"),
    [
        pytest.param(
            "C:\\tcl",
            "C:\\tk",
            [
                '@if NOT "C:\\tcl"=="" @set "TCL_LIBRARY=C:\\tcl"',
                '@if NOT "C:\\tk"=="" @set "TK_LIBRARY=C:\\tk"',
            ],
            ["call :assign TCL_LIBRARY _OLD_VIRTUAL_TCL_LIBRARY", "call :assign TK_LIBRARY _OLD_VIRTUAL_TK_LIBRARY"],
            id="windows",
        ),
        pytest.param(
            None,
            None,
            ['@if NOT ""=="" @set "TCL_LIBRARY="', '@if NOT ""=="" @set "TK_LIBRARY="'],
            [],
            id="missing",
        ),
    ],
)
def test_batch_tkinter_generation(tmp_path, tcl_lib, tk_lib, activate_lines, deactivate_lines) -> None:
    # GIVEN
    class MockInterpreter:
        os = "nt"

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
    activator = BatchActivator(Namespace(prompt=None))

    # WHEN
    activator.generate(creator)
    activate_content = (creator.bin_dir / "activate.bat").read_text(encoding="utf-8")
    deactivate_content = (creator.bin_dir / "deactivate.bat").read_text(encoding="utf-8")

    # THEN
    assert [line for line in activate_lines if line not in activate_content] == []
    assert [line for line in deactivate_lines if line not in deactivate_content] == []


# every field feeds the same character check, so the tcl and tk fields need only one of the characters
@pytest.mark.parametrize(
    ("dest", "libs"),
    [
        pytest.param("env&name", ("lib", "lib"), id="destination-ampersand"),
        pytest.param("env^name", ("lib", "lib"), id="destination-caret"),
        pytest.param("env!name", ("lib", "lib"), id="destination-exclamation"),
        pytest.param("env\u2028name", ("lib", "lib"), id="destination-line-separator"),
        pytest.param("env", ("lib\x1aname", "lib"), id="tcl-end-of-file"),
        pytest.param("env", ("lib&name", "lib"), id="tcl-ampersand"),
        pytest.param("env", ("lib", "lib&name"), id="tk-ampersand"),
    ],
)
def test_batch_skips_changed_paths(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    dest: str,
    libs: tuple[str, str],
) -> None:
    creator: Final[Creator] = session_via_cli([str(tmp_path / dest), "--no-seed"], setup_logging=False).creator
    tcl_lib, tk_lib = libs
    monkeypatch.setattr(creator.interpreter, "tcl_lib", str(tmp_path / tcl_lib), raising=False)
    monkeypatch.setattr(creator.interpreter, "tk_lib", str(tmp_path / tk_lib), raising=False)
    creator.bin_dir.mkdir(parents=True)
    for name in ("activate.bat", "deactivate.bat", "pydoc.bat", "keep.txt"):
        (creator.bin_dir / name).write_text("old", encoding="utf-8")
    assert BatchActivator(VirtualEnvOptions(prompt=None)).generate(creator) == []
    assert list(creator.bin_dir.iterdir()) == [creator.bin_dir / "keep.txt"]
    assert "skipping batch activation scripts" in caplog.text
    assert "cannot preserve" in caplog.text


@pytest.mark.skipif(not IS_WIN, reason="requires cmd.exe")
@pytest.mark.parametrize(
    "name",
    [
        pytest.param("env space", id="space"),
        pytest.param("env(x86)", id="parentheses"),
        pytest.param("env%SECRET%", id="percent"),
    ],
)
@pytest.mark.parametrize("delayed", [pytest.param("OFF", id="normal"), pytest.param("ON", id="delayed-expansion")])
@pytest.mark.parametrize(
    ("set_prompt", "prompt"),
    [
        pytest.param('@set "PROMPT=original"', "original", id="prompt-set"),
        # cmd shows $P$G when PROMPT is undefined, e.g. after a bare `prompt` command
        pytest.param("@set PROMPT=", "$P$G", id="prompt-unset"),
    ],
)
@pytest.mark.parametrize(
    "path_source",
    [
        pytest.param("PATH", id="path-set"),
        # a build script that starts from a clean environment can run `set PATH=` before activating; an undefined
        # variable expands to nothing in a batch file, so taking PATH from it leaves PATH undefined
        pytest.param("VIRTUALENV_UNDEFINED_PATH", id="path-unset"),
    ],
)
# the parametrize fields are passed as separate arguments
def test_batch_path_round_trip(  # ruff:ignore[too-many-arguments]
    tmp_path: Path, name: str, delayed: str, set_prompt: str, prompt: str, path_source: str
) -> None:
    creator: Final[Creator] = session_via_cli([str(tmp_path / name), "--no-seed"], setup_logging=False).creator
    creator.bin_dir.mkdir(parents=True)
    BatchActivator(VirtualEnvOptions(prompt="roundtrip$P")).generate(creator)
    snapshot: Final[str] = (
        f'@"{sys.executable}" -I -c "import json,os; '
        "print(json.dumps({k:os.environ.get(k) for k in ('VIRTUAL_ENV','PATH','PROMPT')}))\""
    )
    (creator.bin_dir / "check.bat").write_text(
        "@echo off\n@set VIRTUAL_ENV=\n@set _OLD_VIRTUAL_PATH=\n@set _OLD_VIRTUAL_PATH_UNSET=\n"
        f'@set _OLD_VIRTUAL_PROMPT=\n{set_prompt}\n@set "PATH=%{path_source}%"\n'
        f"@call activate.bat\n{snapshot}\n@call activate.bat\n{snapshot}\n@call deactivate.bat\n{snapshot}\n"
        # a later activation from another PATH must save that PATH, not state that deactivate left behind
        f'@set "PATH=%SystemRoot%"\n@call activate.bat\n{snapshot}',
        encoding="utf-8",
    )
    result: Final[subprocess.CompletedProcess[str]] = subprocess.run(
        [os.environ["COMSPEC"], "/D", f"/V:{delayed}", "/C", "check.bat"],
        cwd=creator.bin_dir,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
        env={**os.environ, "SECRET": "expanded", "VIRTUAL_ENV_DISABLE_PROMPT": ""},
    )
    active: Final[dict[str, str]] = {
        "VIRTUAL_ENV": str(creator.dest),
        "PATH": f"{creator.bin_dir};{os.environ.get(path_source, '')}",
        "PROMPT": f"(roundtrip$$P) {prompt}",
    }
    assert [json.loads(line) for line in result.stdout.splitlines()] == [
        active,
        active,
        {"VIRTUAL_ENV": None, "PATH": os.environ.get(path_source), "PROMPT": prompt},
        {**active, "PATH": f"{creator.bin_dir};{os.environ['SYSTEMROOT']}"},
    ]
    assert not result.stderr


@pytest.mark.skipif(not IS_WIN, reason="requires cmd.exe")
@pytest.mark.parametrize(
    ("delayed", "before_deactivate"),
    [
        pytest.param("OFF", "", id="normal"),
        pytest.param("ON", "", id="delayed-expansion"),
        pytest.param("OFF", "@setlocal EnableDelayedExpansion\n", id="enable-delayed-before-deactivate"),
        pytest.param("ON", "@setlocal DisableDelayedExpansion\n", id="disable-delayed-before-deactivate"),
    ],
)
@pytest.mark.parametrize("replacement", [pytest.param("", id="empty"), pytest.param("expanded", id="defined")])
def test_batch_path_keeps_exclamation_marks(
    tmp_path: Path, delayed: str, before_deactivate: str, replacement: str
) -> None:
    creator = session_via_cli([str(tmp_path / "env"), "--no-seed"], setup_logging=False).creator
    creator.bin_dir.mkdir(parents=True)
    BatchActivator(VirtualEnvOptions(prompt=None)).generate(creator)
    (creator.bin_dir / "check.bat").write_text(
        "@echo off\n@set _OLD_VIRTUAL_PATH=\n@set _OLD_VIRTUAL_PATH_UNSET=\n"
        f"@call activate.bat\n@set PATH\n{before_deactivate}@call deactivate.bat\n@set PATH\n",
        encoding="utf-8",
    )
    original = rf'"C:\Build ^ tools!q!\bin";{os.environ["SYSTEMROOT"]}\System32'
    result = subprocess.run(
        [os.environ["COMSPEC"], "/D", f"/V:{delayed}", "/C", "check.bat"],
        cwd=creator.bin_dir,
        env={**os.environ, "PATH": original, "q": replacement},
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )

    assert ([line for line in result.stdout.splitlines() if line.startswith("PATH=")], result.stderr) == (
        [f"PATH={creator.bin_dir};{original}", f"PATH={original}"],
        "",
    )


@pytest.mark.skipif(not IS_WIN, reason="requires cmd.exe")
@pytest.mark.parametrize("delayed", [pytest.param("OFF", id="normal"), pytest.param("ON", id="delayed-expansion")])
def test_batch_restores_inherited_values(tmp_path: Path, delayed: str) -> None:
    creator: Final[Creator] = session_via_cli([str(tmp_path / "env"), "--no-seed"], setup_logging=False).creator
    creator.bin_dir.mkdir(parents=True)
    BatchActivator(VirtualEnvOptions(prompt=None)).generate(creator)
    names: Final[tuple[str, ...]] = ("PROMPT", "PYTHONHOME", "TCL_LIBRARY", "TK_LIBRARY", "PKG_CONFIG_PATH")
    inherited: Final[dict[str, str]] = {
        "PROMPT": '"Build ^ tools!q!"$G',
        "PYTHONHOME": r'"C:\Build ^ tools!q!\Python"',
        "TCL_LIBRARY": r'"C:\Build ^ tools!q!\tcl"',
        "TK_LIBRARY": r'"C:\Build ^ tools!q!\tk"',
        "PKG_CONFIG_PATH": r'"C:\Build ^ tools!q!\pkg"',
    }
    snapshot: Final[str] = (
        f'@"{sys.executable}" -I -c "import json,os; print(json.dumps({{k:os.environ.get(k) for k in {names!r}}}))"'
    )
    (creator.bin_dir / "check.bat").write_text(
        f"@echo off\n@call activate.bat\n{snapshot}\n@call deactivate.bat\n{snapshot}\n", encoding="utf-8"
    )
    result: Final[subprocess.CompletedProcess[str]] = subprocess.run(
        [os.environ["COMSPEC"], "/D", f"/V:{delayed}", "/C", "check.bat"],
        cwd=creator.bin_dir,
        env={**os.environ, **inherited, "q": "X", "VIRTUAL_ENV_DISABLE_PROMPT": ""},
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
        check=True,
    )
    active, restored = (json.loads(line) for line in result.stdout.splitlines())
    assert (active["PROMPT"], active["PYTHONHOME"], active["PKG_CONFIG_PATH"]) == (
        f"(env) {inherited['PROMPT']}",
        None,
        f"{creator.dest}\\lib\\pkgconfig;{inherited['PKG_CONFIG_PATH']}",
    )
    assert (restored, result.stderr) == (inherited, "")


def test_batch_quote_replaces_end_of_file() -> None:
    assert BatchActivator.quote("before\x1aafter") == "before after"


@pytest.fixture
def batch_python(activation_python) -> None:
    if not (activation_python.creator.bin_dir / "activate.bat").exists():
        pytest.skip("Batch activation does not support this destination")


@pytest.mark.parametrize("activations", [pytest.param(1, id="activate_once"), pytest.param(2, id="activate_twice")])
@pytest.mark.usefixtures("batch_python")
def test_batch(activation_tester_class, activation_tester, tmp_path, activations) -> None:
    version_script = tmp_path / "version.bat"
    version_script.write_text("ver", encoding="utf-8")

    class Batch(activation_tester_class):
        def __init__(self, session) -> None:
            super().__init__(BatchActivator, session, None, "activate.bat", "bat")
            self._version_cmd = [str(version_script)]
            self._invoke_script = []
            self.deactivate = "call deactivate"
            self.activate_cmd = "call"
            self.pydoc_call = f"call {self.pydoc_call}"
            self.unix_line_ending = False

        def _get_test_lines(self, activate_script):
            return ["@echo off", *super()._get_test_lines(activate_script)]

        def activate_call(self, script):
            # activating again without deactivating must still restore the values from before the first activation
            return " & ".join([super().activate_call(script)] * activations)

        def quote(self, string):
            if '"' in string or " " in string:
                text = string.replace('"', r"\"")
                return f'"{text}"'
            return string

        def print_prompt(self) -> str:
            return 'echo "%PROMPT:$$=$%"'

    activation_tester(Batch)


@pytest.mark.usefixtures("batch_python")
def test_batch_output(activation_tester_class, activation_tester, tmp_path) -> None:
    version_script = tmp_path / "version.bat"
    version_script.write_text("ver", encoding="utf-8")

    class Batch(activation_tester_class):
        def __init__(self, session) -> None:
            super().__init__(BatchActivator, session, None, "activate.bat", "bat")
            self._version_cmd = [str(version_script)]
            self._invoke_script = []
            self.deactivate = "call deactivate"
            self.activate_cmd = "call"
            self.pydoc_call = f"call {self.pydoc_call}"
            self.unix_line_ending = False

        def _get_test_lines(self, activate_script):
            # Build an intermediary script that activates, echoes the current echo setting, then deactivates.
            #
            # This is what proves echo state survives activation and deactivation without leaking unwanted output.
            intermediary_script_path = str(tmp_path / "intermediary.bat")
            activate_script_quoted = self.quote(str(activate_script))
            return [
                "@echo on",
                f"@echo @call {activate_script_quoted} > {intermediary_script_path}",
                f"@echo @echo >> {intermediary_script_path}",
                f"@echo @deactivate >> {intermediary_script_path}",
                f"@call {intermediary_script_path}",
            ]

        def quote(self, string):
            if '"' in string or " " in string:
                text = string.replace('"', r"\"")
                return f'"{text}"'
            return string

        # the base tester calls assert_output with tmp_path, this check does not use it
        def assert_output(self, out, raw, tmp_path) -> None:  # ruff:ignore[unused-method-argument]
            assert out[0] == "ECHO is on.", raw

        def print_prompt(self) -> str:
            return 'echo "%PROMPT:$$=$%"'

    activation_tester(Batch)


@pytest.mark.skipif(sys.platform != "win32", reason="requires Windows batch activation")
def test_batch_removes_stale_script_when_unselected(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG)
    session = session_via_cli(
        [str(tmp_path / "env&name"), "--no-seed", "--activators", "powershell"], setup_logging=False
    )
    session.creator.bin_dir.mkdir(parents=True)
    script = session.creator.bin_dir / "activate.bat"
    script.write_text("old", encoding="utf-8")
    session.run()
    assert not script.exists()
    assert [record.levelno for record in caplog.records if record.message.startswith("skipping batch")] == [
        logging.DEBUG
    ]
