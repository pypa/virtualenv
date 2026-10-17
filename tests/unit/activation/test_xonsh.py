from __future__ import annotations

import copy
import json
import logging
import os
import subprocess
from argparse import Namespace
from ast import literal_eval
from shutil import which
from typing import TYPE_CHECKING, Final
from unittest.mock import create_autospec

import pytest
from python_discovery import PythonInfo

from virtualenv.activation import XonshActivator
from virtualenv.config.cli.parser import VirtualEnvOptions
from virtualenv.create.creator import Creator
from virtualenv.run import cli_run, session_via_cli

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

_NEEDS_XONSH: Final = pytest.mark.skipif(which("xonsh") is None, reason="requires xonsh")


@pytest.fixture
def xonsh() -> Callable[..., str]:
    def run(script: str, **env: str) -> str:
        return subprocess.run(
            ["xonsh", "--no-rc", "-c", script],
            env={k: v for k, v in os.environ.items() if k not in {"PYTHONHOME", "PYTHONWARNDEFAULTENCODING"}} | env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=True,
        ).stdout

    return run


@pytest.mark.parametrize(
    "name",
    [
        pytest.param("env$HOME", id="variable"),
        pytest.param("env${HOME}", id="braces"),
        pytest.param("env=~root", id="home"),
    ],
)
def test_xonsh_skips_expanding_destination(tmp_path: Path, name: str, caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.WARNING)
    session: Final = session_via_cli([str(tmp_path / name), "--no-seed", "--activators", "xonsh"], setup_logging=False)
    session.creator.bin_dir.mkdir(parents=True)
    (script := session.creator.bin_dir / "activate.xsh").write_text("old", encoding="utf-8")
    assert (XonshActivator(VirtualEnvOptions(prompt=None)).generate(session.creator), script.exists()) == ([], False)
    assert caplog.messages == [
        f"skipping xonsh activation script: destination {session.creator.dest} contains path expansion syntax"
    ]


@_NEEDS_XONSH
@pytest.mark.parametrize(
    "original", [pytest.param(None, id="unset"), pytest.param("__virtualenv_was_not_set__", id="sentinel-value")]
)
def test_xonsh_restores_pythonhome_without_exported_sentinel(
    tmp_path: Path, xonsh: Callable[..., str], original: str | None
) -> None:
    session: Final = cli_run([str(tmp_path / "env"), "--no-seed", "--activators", "xonsh"])
    script: Final = (
        "import json\n"
        + ("" if original is None else f"$PYTHONHOME = {original!r}\n")
        + f'source "{session.creator.bin_dir / "activate.xsh"}"\n'
        + "print(json.dumps(__xonsh__.env.get('_OLD_VIRTUAL_PYTHONHOME')))\ndeactivate\n"
        + "print(json.dumps(__xonsh__.env.get('PYTHONHOME')))\n"
    )
    assert [json.loads(line) for line in xonsh(script).splitlines()] == [original, original]


@pytest.mark.parametrize(
    ("tcl_lib", "tk_lib", "present"),
    [
        ("/path/to/tcl", "/path/to/tk", True),
        (None, None, False),
    ],
)
def test_xonsh_tkinter_generation(tmp_path, tcl_lib, tk_lib, present) -> None:
    # GIVEN
    interpreter = create_autospec(PythonInfo, instance=True)
    interpreter.tcl_lib = tcl_lib
    interpreter.tk_lib = tk_lib

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()

    creator = create_autospec(Creator, instance=True)
    creator.dest = tmp_path
    creator.bin_dir = bin_dir
    creator.interpreter = interpreter
    creator.pyenv_cfg = {}
    creator.env_name = "my-env"

    activator = XonshActivator(Namespace(prompt=None))

    # WHEN
    activator.generate(creator)
    content = (bin_dir / "activate.xsh").read_text(encoding="utf-8")

    # THEN
    # `managed_vars` always lists TCL_LIBRARY/TK_LIBRARY so deactivate can clean up
    # whatever activation introduced — regardless of whether the interpreter reported
    # tcl_lib/tk_lib.
    assert '"TCL_LIBRARY"' in content
    assert '"TK_LIBRARY"' in content

    if present:
        # Paths are embedded in __init__ as Python string literals and used
        # from self.embedded_* attributes during activate().
        assert "self.embedded_tcl_library = '/path/to/tcl'" in content
        assert "self.embedded_tk_library = '/path/to/tk'" in content
    else:
        # Empty strings are falsy, so the override loop is skipped at runtime.
        assert "self.embedded_tcl_library = ''" in content
        assert "self.embedded_tk_library = ''" in content


@pytest.mark.parametrize(
    "value",
    [
        pytest.param("hello", id="plain"),
        pytest.param("it's", id="apostrophe"),
        pytest.param("", id="empty"),
        pytest.param("中'\\name", id="unicode-and-quotes"),
    ],
)
def test_xonsh_quote(value: str) -> None:
    assert literal_eval(XonshActivator.quote(value).encode("ascii").decode("gbk")) == value


@_NEEDS_XONSH
def test_xonsh(activation_tester_class, activation_tester) -> None:
    class Xonsh(activation_tester_class):
        def __init__(self, session) -> None:
            super().__init__(XonshActivator, session, "xonsh", "activate.xsh", "xsh")
            self._invoke_script.append("--no-rc")

        def env(self, tmp_path):
            env = super().env(tmp_path)
            # Keep the subprocess hermetic: skip auto-loaded xontribs that a dev may
            # have installed locally, and surface tracebacks so test failures are
            # actionable.
            env["XONTRIBS_AUTOLOAD_DISABLED"] = "1"
            env["XONSH_SHOW_TRACEBACK"] = "1"
            # xonsh runs on its own interpreter, so the EncodingWarnings tox enables come from xonsh's code and would
            # land in the parsed output
            env.pop("PYTHONWARNDEFAULTENCODING", None)
            return env

        def print_prompt(self):
            return 'echo @("(" + $VIRTUAL_ENV_PROMPT + ") ")'

        def assert_pkg_config_path(self, before, activated, deactivated, raw) -> None:
            # activate.xsh does not manage PKG_CONFIG_PATH
            assert before == activated == deactivated, raw

        def activate_call(self, script):
            return f"source {self.quote(str(script))}"

    activation_tester(Xonsh)


@_NEEDS_XONSH
def test_xonsh_switch_restores_unset_tk_libraries(tmp_path: Path, xonsh: Callable[..., str]) -> None:
    activations: Final[list[Path]] = []
    for name, library in (("first", "/test/library"), ("second", None)):
        session = session_via_cli([str(tmp_path / name), "--no-seed", "--activators", "xonsh"])
        session.creator.bin_dir.mkdir(parents=True)
        session.creator.interpreter = copy.copy(session.creator.interpreter)
        session.creator.interpreter.tcl_lib = library
        session.creator.interpreter.tk_lib = library
        activations.extend(XonshActivator(VirtualEnvOptions(prompt=None)).generate(session.creator))
    script: Final = (
        "import json\n"
        "__xonsh__.env.pop('TCL_LIBRARY', None)\n"
        "__xonsh__.env.pop('TK_LIBRARY', None)\n"
        f'source "{activations[0]}"\n'
        f'source "{activations[1]}"\n'
        "print(json.dumps([__xonsh__.env.get('TCL_LIBRARY'), __xonsh__.env.get('TK_LIBRARY')]))\n"
    )
    assert json.loads(xonsh(script)) == [None, None]


@_NEEDS_XONSH
@pytest.mark.parametrize("encoding", [pytest.param("gbk", id="gbk"), pytest.param("big5", id="big5")])
def test_xonsh_preserves_unicode_values(tmp_path: Path, xonsh: Callable[..., str], encoding: str) -> None:
    destination: Final = tmp_path / "中文環境"
    prompt: Final = "中文提示"
    session: Final = cli_run([str(destination), "--no-seed", "--activators", "xonsh", "--prompt", prompt])
    script: Final = (
        f"source @({str(session.creator.bin_dir / 'activate.xsh')!a})\n"
        "import json\nprint(json.dumps([$VIRTUAL_ENV, $VIRTUAL_ENV_PROMPT]))"
    )
    assert json.loads(xonsh(script, XONSH_ENCODING=encoding)) == [str(destination), prompt]
