from __future__ import annotations

import json
import os
import subprocess
import sys
from argparse import Namespace
from typing import TYPE_CHECKING, Final

import pytest

from virtualenv import session_via_cli
from virtualenv.activation import BatchActivator
from virtualenv.config.cli.parser import VirtualEnvOptions
from virtualenv.info import IS_WIN

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture(scope="session")
def special_char_name():
    """Exclude ampersands, which batch activation does not support in paths."""
    base = "'\";e-$ èрт🚒♞中片-j"
    if IS_WIN:
        base = base.replace('"', "").replace(";", "")
    encoding = "ascii" if IS_WIN else sys.getfilesystemencoding()
    result = ""
    for char in base:
        try:
            trip = char.encode(encoding, errors="strict").decode(encoding)
            if char == trip:
                result += char
        except ValueError:  # ruff:ignore[try-except-in-loop]
            continue
    assert result
    return result


def test_batch_pydoc_bat_quoting(tmp_path) -> None:
    """Test that pydoc.bat properly quotes python.exe path to handle spaces."""

    # GIVEN: A mock interpreter
    class MockInterpreter:
        os = "nt"
        tcl_lib = None
        tk_lib = None

    class MockCreator:
        def __init__(self, dest) -> None:
            self.dest = dest
            self.bin_dir = dest / "Scripts"
            self.bin_dir.mkdir(parents=True)
            self.interpreter = MockInterpreter()
            self.pyenv_cfg = {}
            self.env_name = "test-env"

    creator = MockCreator(tmp_path)
    options = Namespace(prompt=None)
    activator = BatchActivator(options)

    # WHEN: Generate activation scripts
    activator.generate(creator)

    # THEN: pydoc.bat should quote python.exe to handle paths with spaces
    pydoc_content = (creator.bin_dir / "pydoc.bat").read_text(encoding="utf-8")

    # The python.exe should be quoted to handle paths with spaces like "C:\Program Files\Python39\python.exe"
    assert '"python.exe"' in pydoc_content, f"python.exe should be quoted in pydoc.bat. Content:\n{pydoc_content}"


@pytest.mark.parametrize(
    ("tcl_lib", "tk_lib", "present"),
    [
        ("C:\\tcl", "C:\\tk", True),
        (None, None, False),
    ],
)
def test_batch_tkinter_generation(tmp_path, tcl_lib, tk_lib, present) -> None:
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
    options = Namespace(prompt=None)
    activator = BatchActivator(options)

    # WHEN
    activator.generate(creator)
    activate_content = (creator.bin_dir / "activate.bat").read_text(encoding="utf-8")
    deactivate_content = (creator.bin_dir / "deactivate.bat").read_text(encoding="utf-8")

    # THEN
    # PKG_CONFIG_PATH is always set
    assert '@if defined PKG_CONFIG_PATH @set "_OLD_PKG_CONFIG_PATH=%PKG_CONFIG_PATH%"' in activate_content
    assert '@set "PKG_CONFIG_PATH=%VIRTUAL_ENV%\\lib\\pkgconfig;%PKG_CONFIG_PATH%"' in activate_content
    assert '@if defined _OLD_PKG_CONFIG_PATH @set "PKG_CONFIG_PATH=%_OLD_PKG_CONFIG_PATH%"' in deactivate_content
    assert "@if not defined _OLD_PKG_CONFIG_PATH @set PKG_CONFIG_PATH=" in deactivate_content
    assert "@set _OLD_PKG_CONFIG_PATH=" in deactivate_content

    if present:
        assert '@if NOT "C:\\tcl"=="" @set "TCL_LIBRARY=C:\\tcl"' in activate_content
        assert '@if NOT "C:\\tk"=="" @set "TK_LIBRARY=C:\\tk"' in activate_content
        assert "if defined _OLD_VIRTUAL_TCL_LIBRARY" in deactivate_content
        assert "if defined _OLD_VIRTUAL_TK_LIBRARY" in deactivate_content
    else:
        assert '@if NOT ""=="" @set "TCL_LIBRARY="' in activate_content
        assert '@if NOT ""=="" @set "TK_LIBRARY="' in activate_content


@pytest.mark.parametrize(
    "character", [pytest.param("&", id="ampersand"), pytest.param("^", id="caret"), pytest.param("!", id="exclamation")]
)
@pytest.mark.parametrize(
    "field",
    [pytest.param("dest", id="destination"), pytest.param("tcl_lib", id="tcl"), pytest.param("tk_lib", id="tk")],
)
def test_batch_skips_changed_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, character: str, field: str
) -> None:
    creator: Final = session_via_cli(
        [str(tmp_path / (f"env{character}name" if field == "dest" else "env")), "--no-seed"],
        setup_logging=False,
    ).creator
    if field != "dest":
        monkeypatch.setattr(creator.interpreter, field, str(tmp_path / f"lib{character}name"), raising=False)
    creator.bin_dir.mkdir(parents=True)
    assert BatchActivator(VirtualEnvOptions(prompt=None)).generate(creator) == []
    assert list(creator.bin_dir.iterdir()) == []
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
def test_batch_path_round_trip(tmp_path: Path, name: str, delayed: str) -> None:
    creator: Final = session_via_cli([str(tmp_path / name), "--no-seed"], setup_logging=False).creator
    creator.bin_dir.mkdir(parents=True)
    BatchActivator(VirtualEnvOptions(prompt="roundtrip")).generate(creator)
    snapshot: Final[str] = (
        f'@"{sys.executable}" -I -c "import json,os; '
        "print(json.dumps({k:os.environ.get(k) for k in ('VIRTUAL_ENV','PATH','PROMPT')}))\""
    )
    (creator.bin_dir / "check.bat").write_text(
        '@echo off\n@set VIRTUAL_ENV=\n@set _OLD_VIRTUAL_PATH=\n@set _OLD_VIRTUAL_PROMPT=\n@set "PROMPT=original"\n'
        f"@call activate.bat\n{snapshot}\n@call activate.bat\n{snapshot}\n@call deactivate.bat\n{snapshot}",
        encoding="utf-8",
    )
    result: Final = subprocess.run(
        [os.environ["COMSPEC"], "/D", f"/V:{delayed}", "/C", "check.bat"],
        cwd=creator.bin_dir,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
        env={**os.environ, "SECRET": "expanded", "VIRTUAL_ENV_DISABLE_PROMPT": ""},
    )
    active: Final = {
        "VIRTUAL_ENV": str(creator.dest),
        "PATH": f"{creator.bin_dir};{os.environ['PATH']}",
        "PROMPT": "(roundtrip) original",
    }
    assert [json.loads(line) for line in result.stdout.splitlines()] == [
        active,
        active,
        {"VIRTUAL_ENV": None, "PATH": os.environ["PATH"], "PROMPT": "original"},
    ]


@pytest.mark.parametrize("activations", [1, 2], ids=["activate_once", "activate_twice"])
def test_batch(activation_python, activation_tester_class, activation_tester, tmp_path, activations) -> None:
    if not (activation_python.creator.bin_dir / "activate.bat").exists():
        pytest.skip("Batch activation does not support this destination")
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

        def quote(self, s):
            if '"' in s or " " in s:
                text = s.replace('"', r"\"")
                return f'"{text}"'
            return s

        def print_prompt(self) -> str:
            return 'echo "%PROMPT%"'

    activation_tester(Batch)


def test_batch_output(activation_python, activation_tester_class, activation_tester, tmp_path) -> None:
    if not (activation_python.creator.bin_dir / "activate.bat").exists():
        pytest.skip("Batch activation does not support this destination")
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
            """Build an intermediary script that activates, echoes the current echo setting, then deactivates.

            This is what proves echo state survives activation and deactivation without leaking unwanted output.

            """
            intermediary_script_path = str(tmp_path / "intermediary.bat")
            activate_script_quoted = self.quote(str(activate_script))
            return [
                "@echo on",
                f"@echo @call {activate_script_quoted} > {intermediary_script_path}",
                f"@echo @echo >> {intermediary_script_path}",
                f"@echo @deactivate >> {intermediary_script_path}",
                f"@call {intermediary_script_path}",
            ]

        def assert_output(self, out, raw, tmp_path) -> None:  # ruff:ignore[unused-method-argument]
            assert out[0] == "ECHO is on.", raw

        def quote(self, s):
            if '"' in s or " " in s:
                text = s.replace('"', r"\"")
                return f'"{text}"'
            return s

        def print_prompt(self) -> str:
            return 'echo "%PROMPT%"'

    activation_tester(Batch)
