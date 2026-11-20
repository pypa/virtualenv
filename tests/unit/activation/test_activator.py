from __future__ import annotations

import os
from argparse import Namespace
from copy import copy
from typing import TYPE_CHECKING, Final

import pytest
from prompt_matrix import PROMPT_CASES, SHELLS, generate_script, prompt_shown, run_prompt, unavailable_mark

from virtualenv.activation.activator import Activator
from virtualenv.activation.bash import BashActivator
from virtualenv.activation.cshell import CShellActivator
from virtualenv.activation.fish import FishActivator
from virtualenv.activation.nushell import NushellActivator
from virtualenv.activation.powershell import PowerShellActivator
from virtualenv.activation.xonsh import XonshActivator
from virtualenv.info import IS_PYPY, IS_WIN
from virtualenv.run import session_via_cli

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path
    from subprocess import CompletedProcess

    from virtualenv.activation.via_template import ViaTemplateActivator
    from virtualenv.create.creator import Creator


@pytest.fixture(scope="module")
def library_creator(tmp_path_factory: pytest.TempPathFactory) -> Creator:
    creator = session_via_cli([
        str(tmp_path_factory.mktemp("library-creator") / "env"),
        "--no-seed",
        "--activators",
        "bash",
    ]).creator
    creator.interpreter = copy(creator.interpreter)
    return creator


@pytest.fixture
def library_environment(monkeypatch: pytest.MonkeyPatch) -> Callable[[bytes | None], None]:
    def set_library(path: bytes | None) -> None:
        for name in (b"TCL_LIBRARY", b"TK_LIBRARY"):
            if path is None:
                monkeypatch.delenv(name.decode(), raising=False)
            else:
                monkeypatch.setitem(os.environb, name, path)

    return set_library


@pytest.mark.skipif(IS_WIN, reason="POSIX activation uses raw environment bytes")
@pytest.mark.parametrize(
    "activator_type",
    [
        pytest.param(BashActivator, id="bash"),
        pytest.param(CShellActivator, id="cshell"),
        pytest.param(FishActivator, id="fish"),
        pytest.param(NushellActivator, id="nushell"),
        pytest.param(PowerShellActivator, id="powershell"),
        pytest.param(XonshActivator, id="xonsh"),
    ],
)
@pytest.mark.parametrize(
    "library_case",
    [
        pytest.param(("/library/andré/tcl8.6", b"/library/andr\xc3\xa9/tcl8.6", "/library/andré/tcl8.6"), id="utf8"),
        pytest.param(("/library/andrÃ©/tcl8.6", b"/library/andr\xc3\xa9/tcl8.6", ""), id="c-locale"),
        pytest.param(("/library/andré/tcl8.6", b"/library/andr\xe9/tcl8.6", ""), id="latin1"),
        pytest.param(("/library/andré/tcl8.6", None, ""), id="cached-without-source"),
        pytest.param(("/library/tcl8.6", None, "/library/tcl8.6"), id="ascii"),
        pytest.param(("/library/andr\udcff/tcl8.6", b"/library/andr\xff/tcl8.6", ""), id="surrogate"),
    ],
)
def test_activation_library_paths_keep_original_bytes(
    library_creator: Creator,
    monkeypatch: pytest.MonkeyPatch,
    library_environment: Callable[[bytes | None], None],
    activator_type: type[ViaTemplateActivator],
    library_case: tuple[str, bytes | None, str],
) -> None:
    library_path, environment_path, expected = library_case
    monkeypatch.setattr(library_creator.interpreter, "tcl_lib", library_path)
    monkeypatch.setattr(library_creator.interpreter, "tk_lib", library_path)
    library_environment(environment_path)
    values = activator_type(Namespace(prompt=None)).replacements(library_creator, library_creator.bin_dir)
    assert (values["__TCL_LIBRARY__"], values["__TK_LIBRARY__"]) == (expected, expected)


@pytest.mark.skipif(IS_WIN, reason="POSIX activation uses raw environment bytes")
@pytest.mark.parametrize(
    ("tcl_source", "expected"),
    [
        pytest.param(
            b"/library/andr\xc3\xa9/tcl8.6",
            ("/library/andré/tcl8.6", "/library/andré/tk8.6"),
            id="verified-tcl",
        ),
        pytest.param(b"/library/andr\xe9/tcl8.6", ("", ""), id="different-tcl-source-bytes"),
    ],
)
def test_derived_tk_path_keeps_verified_tcl_bytes(
    library_creator: Creator,
    monkeypatch: pytest.MonkeyPatch,
    tcl_source: bytes,
    expected: tuple[str, str],
) -> None:
    monkeypatch.setattr(library_creator.interpreter, "tcl_lib", "/library/andré/tcl8.6")
    monkeypatch.setattr(library_creator.interpreter, "tk_lib", "/library/andré/tk8.6")
    monkeypatch.setitem(os.environb, b"TCL_LIBRARY", tcl_source)
    monkeypatch.delenv("TK_LIBRARY", raising=False)
    values = BashActivator(Namespace(prompt=None)).replacements(library_creator, library_creator.bin_dir)
    assert (values["__TCL_LIBRARY__"], values["__TK_LIBRARY__"]) == expected


@pytest.mark.skipif(IS_WIN, reason="POSIX activation uses raw environment bytes")
def test_explicit_tk_path_requires_its_own_bytes(library_creator: Creator, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(library_creator.interpreter, "tcl_lib", "/library/andré/tcl8.6")
    monkeypatch.setattr(library_creator.interpreter, "tk_lib", "/library/andré/tk8.6")
    monkeypatch.setitem(os.environb, b"TCL_LIBRARY", b"/library/andr\xc3\xa9/tcl8.6")
    monkeypatch.setitem(os.environb, b"TK_LIBRARY", b"/library/andr\xe9/tk8.6")
    values = BashActivator(Namespace(prompt=None)).replacements(library_creator, library_creator.bin_dir)
    assert (values["__TCL_LIBRARY__"], values["__TK_LIBRARY__"]) == ("/library/andré/tcl8.6", "")


@pytest.mark.graalpy
def test_activator_prompt_cwd(monkeypatch, tmp_path) -> None:
    class FakeActivator(Activator):
        def generate(self, creator):
            raise NotImplementedError

    cwd = tmp_path / "magic"
    cwd.mkdir()
    monkeypatch.chdir(cwd)

    activator = FakeActivator(Namespace(prompt="."))
    assert activator.flag_prompt == "magic"


@pytest.mark.skipif(IS_PYPY, reason="quoting does not depend on the interpreter, the CPython jobs run this matrix")
@pytest.mark.slow
@pytest.mark.parametrize(
    "case",
    [pytest.param(case, id="-".join(case), marks=unavailable_mark(case[0], case[2])) for case in PROMPT_CASES],
)
def test_activator_prompt_stays_data(tmp_path: Path, case: tuple[str, str, str, str]) -> None:
    shell, state, action, payload = case
    prompt: Final[str] = SHELLS[shell].payloads[payload]
    result: Final[CompletedProcess[str]] = run_prompt(
        shell, generate_script(shell, tmp_path / "env", prompt), state, action, tmp_path
    )

    assert ((tmp_path / "PWNED").exists(), prompt_shown(shell, result, prompt, state, action)) == (False, True), (
        result.stdout + result.stderr
    )
