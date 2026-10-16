from __future__ import annotations

import json
import os
import subprocess
from argparse import Namespace
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
    from pathlib import Path


@pytest.mark.parametrize(
    "name",
    [
        pytest.param("env$HOME", id="variable"),
        pytest.param("env${HOME}", id="braces"),
        pytest.param("env=~root", id="home"),
    ],
)
def test_xonsh_skips_expanding_destination(tmp_path: Path, name: str) -> None:
    session: Final = session_via_cli([str(tmp_path / name), "--no-seed", "--activators", "xonsh"])
    session.creator.bin_dir.mkdir(parents=True)
    (session.creator.bin_dir / "activate.xsh").write_text("old", encoding="utf-8")
    XonshActivator(VirtualEnvOptions(prompt=None)).generate(session.creator)
    assert not (session.creator.bin_dir / "activate.xsh").exists()


@pytest.mark.skipif(which("xonsh") is None, reason="requires xonsh")
@pytest.mark.parametrize(
    "original", [pytest.param(None, id="unset"), pytest.param("__virtualenv_was_not_set__", id="sentinel-value")]
)
def test_xonsh_restores_pythonhome_without_exported_sentinel(tmp_path: Path, original: str | None) -> None:
    session: Final = cli_run([str(tmp_path / "env"), "--no-seed", "--activators", "xonsh"])
    script: Final = (
        "import json\n"
        + ("__xonsh__.env.pop('PYTHONHOME', None)\n" if original is None else f"$PYTHONHOME = {original!r}\n")
        + f'source "{session.creator.bin_dir / "activate.xsh"}"\n'
        + "print(json.dumps(__xonsh__.env.get('_OLD_VIRTUAL_PYTHONHOME')))\ndeactivate\n"
        + "print(json.dumps(__xonsh__.env.get('PYTHONHOME')))\n"
    )
    assert [
        json.loads(line)
        for line in subprocess.run(
            ["xonsh", "--no-rc", "-c", script],
            env={
                key: value
                for key, value in os.environ.items()
                if key not in {"PYTHONHOME", "PYTHONWARNDEFAULTENCODING"}
            },
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=True,
        ).stdout.splitlines()
    ] == [original, original]


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


def test_xonsh_quote() -> None:
    # XonshActivator.quote uses repr() so the template substitution produces valid
    # Python literals — this is what the rest of the tests rely on.
    assert XonshActivator.quote("hello") == "'hello'"
    assert XonshActivator.quote("it's") == '"it\'s"'
    assert XonshActivator.quote("") == "''"


@pytest.mark.skipif(which("xonsh") is None, reason="xonsh is not installed")
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
