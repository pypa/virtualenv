from __future__ import annotations

import copy
import json
import logging
import os
import subprocess
import sys
from argparse import Namespace
from ast import literal_eval
from shutil import which
from typing import TYPE_CHECKING, Final, Protocol

import pytest
from python_discovery import PythonInfo

from virtualenv.activation import XonshActivator
from virtualenv.config.cli.parser import VirtualEnvOptions
from virtualenv.create.creator import Creator
from virtualenv.info import IS_WIN
from virtualenv.run import cli_run, session_via_cli

if TYPE_CHECKING:
    from pathlib import Path

    from virtualenv.run.session import Session

_NEEDS_XONSH: Final[pytest.MarkDecorator] = pytest.mark.skipif(which("xonsh") is None, reason="requires xonsh")


class _Xonsh(Protocol):
    def __call__(self, script: str, **env: str) -> str: ...


@pytest.fixture
def xonsh() -> _Xonsh:
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
    session: Final[Session] = session_via_cli(
        [str(tmp_path / name), "--no-seed", "--activators", "xonsh"], setup_logging=False
    )
    session.creator.bin_dir.mkdir(parents=True)
    (script := session.creator.bin_dir / "activate.xsh").write_text("old", encoding="utf-8")
    assert (XonshActivator(VirtualEnvOptions(prompt=None)).generate(session.creator), script.exists()) == ([], False)
    assert caplog.messages == [
        f"skipping xonsh activation script: destination {session.creator.dest} contains path expansion syntax"
    ]


@_NEEDS_XONSH
@pytest.mark.parametrize(
    ("prelude", "original"),
    [
        pytest.param("", None, id="unset"),
        pytest.param("$PYTHONHOME = '__virtualenv_was_not_set__'\n", "__virtualenv_was_not_set__", id="sentinel-value"),
    ],
)
def test_xonsh_restores_pythonhome_without_exported_sentinel(
    tmp_path: Path, xonsh: _Xonsh, prelude: str, original: str | None
) -> None:
    session: Final[Session] = cli_run([str(tmp_path / "env"), "--no-seed", "--activators", "xonsh"])
    activate: Final[Path] = session.creator.bin_dir / "activate.xsh"
    script: Final[str] = (
        f'import json\n{prelude}source "{activate}"\n'
        "print(json.dumps(__xonsh__.env.get('_OLD_VIRTUAL_PYTHONHOME')))\n"
        "print(json.dumps(__xonsh__.env.get('PYTHONHOME')))\ndeactivate\n"
        "print(json.dumps(__xonsh__.env.get('PYTHONHOME')))\n"
    )
    assert [json.loads(line) for line in xonsh(script).splitlines()] == [original, None, original]


@pytest.mark.parametrize(
    ("tcl_lib", "tk_lib"),
    [
        pytest.param("/path/to/tcl", "/path/to/tk", id="present"),
        pytest.param(None, None, id="missing"),
        pytest.param(
            "C:/andré/tcl",
            "C:/andré/tk",
            id="windows-unicode",
            marks=pytest.mark.skipif(not IS_WIN, reason="requires Windows path encoding"),
        ),
    ],
)
def test_xonsh_tkinter_generation(mocker, tmp_path, tcl_lib, tk_lib) -> None:
    # GIVEN
    interpreter = mocker.create_autospec(PythonInfo, instance=True, tcl_lib=tcl_lib, tk_lib=tk_lib)

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()

    creator = mocker.create_autospec(
        Creator, instance=True, dest=tmp_path, bin_dir=bin_dir, interpreter=interpreter, pyenv_cfg={}, env_name="my-env"
    )

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

    assignments = "\n".join(
        line.strip()
        for line in content.splitlines()
        if line.strip().startswith(("self.embedded_tcl_library = ", "self.embedded_tk_library = "))
    )
    code = (
        "import json\nfrom types import SimpleNamespace\n"
        "self = SimpleNamespace(_fs_path=lambda value, required=False: value)\n"
        f"{assignments}\n"
        "print(json.dumps((self.embedded_tcl_library, self.embedded_tk_library)))"
    )
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, encoding="utf-8", check=True)
    assert json.loads(result.stdout) == [tcl_lib or "", tk_lib or ""]


@pytest.mark.parametrize(
    "value",
    [
        pytest.param("hello", id="plain"),
        pytest.param("", id="empty"),
    ],
)
def test_xonsh_quote(value: str) -> None:
    assert literal_eval(XonshActivator.quote(value).encode("ascii").decode("gbk")) == value


@pytest.mark.parametrize(
    "value",
    [
        pytest.param("it's", id="apostrophe"),
        pytest.param("中'\\name", id="unicode-backslash"),
        pytest.param("a+ACc-b", id="utf7-shift"),
        pytest.param("x~{y", id="hz-shift"),
        pytest.param("100%", id="percent"),
        pytest.param("\udcff\x7f", id="surrogate-control"),
    ],
)
@pytest.mark.parametrize(
    "encoding", [pytest.param(name, id=name) for name in ("utf-7", "hz", "cp864", "shift_jis_2004", "unicode_escape")]
)
def test_xonsh_quote_survives_source_codec(value: str, encoding: str) -> None:
    source = XonshActivator.quote(value).encode("ascii").decode(encoding)
    result = subprocess.run(
        [sys.executable, "-c", f"print(repr({source}))"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    assert literal_eval(result.stdout) == value


@_NEEDS_XONSH
@pytest.mark.parametrize(
    "case",
    [
        pytest.param(("it's", "env", "gbk", ""), id="apostrophe-gbk"),
        pytest.param(("中'\\name", "env", "gbk", ""), id="unicode-and-quotes-gbk"),
        pytest.param(("prefix+ACc-suffix", "env", "utf-7", ""), id="encoded-quote-utf7"),
        pytest.param(("café", "env", "utf-7", ""), id="unicode-utf7"),
        pytest.param(("label", "env+ACc-tail", "utf-7", ""), id="encoded-quote-destination"),
        pytest.param(("it's", "env", "utf-7", "chr = 'shadow'\nmap = 'shadow'\n"), id="shadowed-builtins"),
    ],
)
def test_xonsh_keeps_prompt_with_source_encoding(
    tmp_path: Path, xonsh: _Xonsh, case: tuple[str, str, str, str]
) -> None:
    prompt, name, encoding, prelude = case
    session: Final[Session] = cli_run([str(tmp_path / name), "--no-seed", "--activators", "xonsh", "--prompt", prompt])
    activate: Final[Path] = session.creator.bin_dir / "activate.xsh"
    assert xonsh(
        f"{prelude}source @({str(activate)!a})\nprint($VIRTUAL_ENV.encode('utf-8').hex())\n"
        'print($VIRTUAL_ENV_PROMPT.encode("utf-8").hex())',
        XONSH_ENCODING=encoding,
    ) == (f"{str(session.creator.dest).encode('utf-8').hex()}\n{prompt.encode('utf-8').hex()}\n")


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

        def activate_call(self, script):
            return f"source {self.quote(str(script))}"

        def quote(self, string):
            return f"@({self.of_class.quote(string)})"

    activation_tester(Xonsh)


@_NEEDS_XONSH
@pytest.mark.parametrize(
    ("prelude", "envs", "expected"),
    [
        pytest.param("", ("first",), "None", id="no-alias"),
        pytest.param('aliases["pydoc"] = "echo mine"\n', ("first",), "['echo', 'mine']", id="own-alias"),
        pytest.param('aliases["pydoc"] = "echo mine"\n', ("first", "second"), "['echo', 'mine']", id="switch"),
    ],
)
def test_xonsh_deactivate_restores_pydoc_alias(
    tmp_path: Path, xonsh: _Xonsh, prelude: str, envs: tuple[str, ...], expected: str
) -> None:
    activations: Final[list[Path]] = [
        cli_run([str(tmp_path / env), "--no-seed", "--activators", "xonsh"]).creator.bin_dir / "activate.xsh"
        for env in envs
    ]
    script: Final[str] = (
        prelude + "".join(f'source "{path}"\n' for path in activations) + 'deactivate\nprint(aliases.get("pydoc"))\n'
    )

    assert xonsh(script).strip() == expected


@_NEEDS_XONSH
def test_xonsh_deactivate_keeps_chained_pydoc_alias(tmp_path: Path, xonsh: _Xonsh) -> None:
    session = cli_run([str(tmp_path / "env"), "--no-seed", "--activators", "xonsh"])
    script = (
        'aliases["viewer"] = ["echo", "before"]\n'
        'aliases["pydoc"] = ["viewer", "docs"]\n'
        f'source "{session.creator.bin_dir / "activate.xsh"}"\n'
        "deactivate\n"
        'aliases["viewer"] = ["echo", "after"]\n'
        "pydoc\n"
    )

    assert xonsh(script).strip() == "after docs"


@_NEEDS_XONSH
def test_xonsh_switch_restores_unset_tk_libraries(tmp_path: Path, xonsh: _Xonsh) -> None:
    activations: Final[list[Path]] = []
    for name, library in (("first", "/test/library"), ("second", None)):
        session = session_via_cli([str(tmp_path / name), "--no-seed", "--activators", "xonsh"])
        session.creator.bin_dir.mkdir(parents=True)
        session.creator.interpreter = copy.copy(session.creator.interpreter)
        session.creator.interpreter.tcl_lib = library
        session.creator.interpreter.tk_lib = library
        activations.extend(XonshActivator(VirtualEnvOptions(prompt=None)).generate(session.creator))
    script: Final[str] = (
        "import json\n"
        "__xonsh__.env.pop('TCL_LIBRARY', None)\n"
        "__xonsh__.env.pop('TK_LIBRARY', None)\n"
        f'source "{activations[0]}"\n'
        f'source "{activations[1]}"\n'
        "print(json.dumps([__xonsh__.env.get('TCL_LIBRARY'), __xonsh__.env.get('TK_LIBRARY')]))\n"
    )
    assert json.loads(xonsh(script)) == [None, None]


@_NEEDS_XONSH
@pytest.mark.skipif(os.name == "nt", reason="requires POSIX environment bytes")
@pytest.mark.parametrize(
    "case",
    [
        pytest.param(("andré", "utf-8", ""), id="utf8-source"),
        pytest.param(("andré+AGE-marker", "utf-7", ""), id="utf7-source"),
        pytest.param(("andré+AGE-marker", "utf-7", "bytes = 'shadow'\n"), id="shadowed-bytes"),
    ],
)
def test_xonsh_keeps_tcl_library_bytes_across_locales(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, xonsh: _Xonsh, case: tuple[str, str, str]
) -> None:
    name, encoding, prelude = case
    library = tmp_path / name / "tcl9.0"
    library.mkdir(parents=True)
    session = cli_run([str(tmp_path / "env"), "--no-seed", "--activators", "xonsh"])
    session.creator.interpreter = copy.copy(session.creator.interpreter)
    session.creator.interpreter.tcl_lib = str(library)
    monkeypatch.setitem(os.environb, b"TCL_LIBRARY", os.fsencode(library))
    XonshActivator(Namespace(prompt=None)).generate(session.creator)
    script = (
        f"{prelude}original = __xonsh__.env.pop('TCL_LIBRARY', None)\n"
        f"source @({str(session.creator.bin_dir / 'activate.xsh')!a})\n"
        "python -c \"import os; print(repr(os.environb.get(b'TCL_LIBRARY')))\""
    )
    assert literal_eval(xonsh(script, LC_ALL="C", PYTHONUTF8="0", XONSH_ENCODING=encoding)) == os.fsencode(library)


@_NEEDS_XONSH
@pytest.mark.skipif(os.name == "nt", reason="requires POSIX environment bytes")
def test_xonsh_keeps_environment_path_bytes_across_locales(tmp_path: Path, xonsh: _Xonsh) -> None:
    destination = tmp_path / "café"
    session = cli_run([str(destination), "--no-seed", "--activators", "xonsh"])
    script = (
        "import json, os\n"
        f"source @(os.fsdecode({os.fsencode(session.creator.bin_dir / 'activate.xsh')!r}))\n"
        "paths = $VIRTUAL_ENV, $PATH[0], $PKG_CONFIG_PATH[0]\n"
        "print(json.dumps([os.fsencode(path).hex() for path in paths]))\n"
    )
    expected = [destination, session.creator.bin_dir, destination / "lib" / "pkgconfig"]
    assert json.loads(xonsh(script, LC_ALL="C", PYTHONUTF8="0", PYTHONCOERCECLOCALE="0")) == [
        os.fsencode(path).hex() for path in expected
    ]


@_NEEDS_XONSH
@pytest.mark.parametrize("encoding", [pytest.param("gbk", id="gbk"), pytest.param("big5", id="big5")])
def test_xonsh_preserves_unicode_values(tmp_path: Path, xonsh: _Xonsh, encoding: str) -> None:
    destination: Final[Path] = tmp_path / "中文環境"
    prompt: Final[str] = "中文提示"
    session: Final[Session] = cli_run([str(destination), "--no-seed", "--activators", "xonsh", "--prompt", prompt])
    script: Final[str] = (
        f"source @({str(session.creator.bin_dir / 'activate.xsh')!a})\n"
        "import json\nprint(json.dumps([$VIRTUAL_ENV, $VIRTUAL_ENV_PROMPT]))"
    )
    assert json.loads(xonsh(script, XONSH_ENCODING=encoding)) == [str(destination), prompt]


@_NEEDS_XONSH
@pytest.mark.skipif(os.name == "nt", reason="requires POSIX environment bytes")
def test_xonsh_keeps_active_environment_when_destination_cannot_round_trip(
    tmp_path: Path, xonsh: _Xonsh, big5_locale: dict[str, str]
) -> None:
    previous = cli_run([str(tmp_path / "previous"), "--no-seed", "--activators", "xonsh"])
    target = cli_run([str(tmp_path / "ぢΑ"), "--no-seed", "--activators", "xonsh"])
    (link := tmp_path / "activate.xsh").symlink_to(target.creator.bin_dir / "activate.xsh")
    script = (
        "import json, subprocess\n"
        f"source @({str(previous.creator.bin_dir / 'activate.xsh')!a})\n"
        "try:\n"
        f"    source @({str(link)!a})\n"
        "except subprocess.CalledProcessError:\n"
        "    print(json.dumps([__xonsh__.env.get('VIRTUAL_ENV'), $PATH[0], 'pydoc' in aliases]))\n"
        "    raise"
    )
    with pytest.raises(subprocess.CalledProcessError) as error:
        xonsh(script, **big5_locale)
    assert "the filesystem codec cannot represent" in error.value.stderr
    assert json.loads(error.value.stdout) == [str(previous.creator.dest), str(previous.creator.bin_dir), True]


@pytest.fixture
def big5_locale(xonsh: _Xonsh) -> dict[str, str]:
    env = {"LC_ALL": "zh_TW.big5", "PYTHONUTF8": "0", "PYTHONCOERCECLOCALE": "0"}
    if xonsh("import sys\nprint(sys.getfilesystemencoding())", **env).strip() != "big5":
        pytest.skip("requires the zh_TW.big5 locale")
    return env


@_NEEDS_XONSH
@pytest.mark.skipif(os.name == "nt", reason="requires POSIX environment bytes")
def test_xonsh_keeps_library_when_codec_cannot_round_trip(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, xonsh: _Xonsh, big5_locale: dict[str, str]
) -> None:
    library = tmp_path / "ぢΑ" / "tcl9.0"
    library.mkdir(parents=True)
    monkeypatch.setitem(os.environb, b"TCL_LIBRARY", os.fsencode(library))
    session = cli_run([str(tmp_path / "env"), "--no-seed", "--activators", "xonsh"])
    session.creator.interpreter = copy.copy(session.creator.interpreter)
    session.creator.interpreter.tcl_lib = str(library)
    XonshActivator(Namespace(prompt=None)).generate(session.creator)
    script = (
        "original = __xonsh__.env.pop('TCL_LIBRARY', None)\n"
        f"source @({str(session.creator.bin_dir / 'activate.xsh')!a})\n"
        "print(repr(__xonsh__.env.get('TCL_LIBRARY')))"
    )
    assert xonsh(script, **big5_locale).strip() == "None"
