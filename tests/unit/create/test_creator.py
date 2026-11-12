from __future__ import annotations

import ast
import difflib
import gc
import json
import logging
import os
import shutil
import site
import stat
import subprocess
import sys
import textwrap
import zipfile
from argparse import ArgumentTypeError
from collections import OrderedDict
from functools import partial
from operator import attrgetter
from pathlib import Path
from stat import S_IREAD, S_IRGRP, S_IROTH
from textwrap import dedent
from threading import Thread
from typing import TYPE_CHECKING, Final, NamedTuple

import pytest
from python_discovery import PythonInfo

from virtualenv.__main__ import run, run_with_catch
from virtualenv.create.creator import DEBUG_SCRIPT, Creator, get_env_debug_info
from virtualenv.create.pyenv_cfg import PyEnvCfg
from virtualenv.create.via_global_ref import api
from virtualenv.create.via_global_ref.api import ViaGlobalRefApi
from virtualenv.create.via_global_ref.builtin.cpython.common import is_mac_os_framework, is_macos_brew
from virtualenv.info import IS_GRAALPY, IS_PYPY, IS_WIN, fs_is_case_sensitive, fs_supports_symlink
from virtualenv.run import cli_run, session_via_cli
from virtualenv.run.plugin.creators import CreatorSelector
from virtualenv.util.error import ProcessCallFailedError

if TYPE_CHECKING:
    from collections.abc import Callable

    from pytest_mock import MockerFixture

    from virtualenv.run.session import Session

_CURRENT: Final[PythonInfo] = PythonInfo.current_system()


@pytest.mark.skipif(not fs_supports_symlink(), reason="symlinks are unavailable")
@pytest.mark.parametrize(
    ("args", "clear_env"),
    [
        pytest.param(["--clear", "link"], "0", id="before-dest"),
        pytest.param(["link", "--clear"], "0", id="after-dest"),
        pytest.param(["link"], "1", id="environment"),
        pytest.param(["missing/../link", "--clear"], "0", id="missing-parent"),
        pytest.param(["link/child/..", "--clear"], "0", id="child-parent"),
    ],
)
def test_clear_rejects_linked_destination(
    linked_destination: Path, args: list[str], clear_env: str, capsys: pytest.CaptureFixture[str]
) -> None:
    marker: Final = linked_destination / "keep.txt"
    marker.write_text("keep", encoding="utf-8")
    with pytest.raises(SystemExit) as context:
        cli_run(
            [arg if arg == "--clear" else str(linked_destination.parent / arg) for arg in args] + ["--no-seed"],
            env={**os.environ, "VIRTUALENV_CLEAR": clear_env},
        )
    assert (
        context.value.code,
        marker.read_text(encoding="utf-8"),
        linked_destination.is_symlink(),
        "--clear cannot use a symlink destination" in capsys.readouterr().err,
    ) == (2, "keep", True, True)


@pytest.mark.skipif(not IS_WIN, reason="requires Windows junctions")
def test_clear_rejects_junction(tmp_path: Path) -> None:
    target: Final = tmp_path / "target"
    target.mkdir()
    junction: Final = tmp_path / "junction"
    subprocess.run(["cmd", "/c", "mklink", "/J", str(junction), str(target)], check=True, capture_output=True)
    with pytest.raises(SystemExit) as context:
        session_via_cli([str(junction), "--clear", "--no-seed"])
    assert context.value.code == 2


@pytest.mark.skipif(not fs_supports_symlink(), reason="symlinks are unavailable")
def test_create_linked_destination_without_clear(linked_destination: Path) -> None:
    session: Final = cli_run([str(linked_destination), "--no-seed"])
    assert (
        session.creator.dest,
        linked_destination.is_symlink(),
        (linked_destination / "pyvenv.cfg").is_file(),
    ) == (linked_destination.resolve(), True, True)


@pytest.fixture
def linked_destination(tmp_path: Path) -> Path:
    target: Final = tmp_path / "target"
    target.mkdir()
    link: Final = tmp_path / "link"
    link.symlink_to(target, target_is_directory=True)
    return link


@pytest.mark.skipif(not fs_supports_symlink(), reason="symlinks are unavailable")
@pytest.mark.parametrize(
    "destination",
    [pytest.param("target", id="direct"), pytest.param("parent/target", id="linked-parent")],
)
def test_clear_direct_destination(tmp_path: Path, destination: str) -> None:
    target: Final = tmp_path / "target"
    target.mkdir()
    marker: Final = target / "old.txt"
    marker.write_text("old", encoding="utf-8")
    link: Final = tmp_path / "parent"
    link.symlink_to(tmp_path, target_is_directory=True)
    session: Final = cli_run([str(tmp_path / destination), "--clear", "--no-seed"])
    assert (session.creator.dest, marker.exists(), (target / "pyvenv.cfg").is_file()) == (target.resolve(), False, True)


_SKIP_WITHOUT_PYTHON39: Final[pytest.MarkDecorator] = pytest.mark.skipif(
    shutil.which("python3.9") is None, reason="Python 3.9 is unavailable"
)


class _GeneratedFile(NamedTuple):
    name: str
    folder: Callable[[Creator], Path]
    extra_args: list[str]


@pytest.mark.parametrize("creator_name", [pytest.param("builtin", id="builtin"), pytest.param("venv", id="venv")])
@pytest.mark.parametrize("link_to", [pytest.param("original", id="existing"), pytest.param("missing", id="dangling")])
@pytest.mark.parametrize(
    "generated",
    [
        pytest.param(_GeneratedFile("pyvenv.cfg", attrgetter("dest"), []), id="pyvenv.cfg"),
        pytest.param(_GeneratedFile("activate", attrgetter("bin_dir"), []), id="activate"),
        pytest.param(_GeneratedFile("pip.exe" if IS_WIN else "pip", attrgetter("bin_dir"), []), id="pip"),
        pytest.param(_GeneratedFile("CACHEDIR.TAG", attrgetter("dest"), []), id="CACHEDIR.TAG"),
        pytest.param(_GeneratedFile(".gitignore", attrgetter("dest"), []), id=".gitignore"),
        pytest.param(
            _GeneratedFile("_virtualenv.py", attrgetter("purelib"), ["--python", "python3.9"]),
            id="_virtualenv.py",
            marks=_SKIP_WITHOUT_PYTHON39,
        ),
        pytest.param(
            _GeneratedFile("_virtualenv.pth", attrgetter("purelib"), ["--python", "python3.9"]),
            id="_virtualenv.pth",
            marks=_SKIP_WITHOUT_PYTHON39,
        ),
    ],
)
def test_creator_replaces_generated_file_links(
    tmp_path: Path,
    creator_name: str,
    link_to: str,
    generated: _GeneratedFile,
) -> None:
    command: Final = [
        str(tmp_path / "env"),
        "--creator",
        creator_name,
        "--pip",
        "embed",
        "--no-periodic-update",
        *generated.extra_args,
    ]
    session: Final = session_via_cli(command)
    session.creator.bin_dir.mkdir(parents=True)
    target: Final = session.creator.dest / "original"
    target.write_bytes(b"original")
    path: Final = generated.folder(session.creator) / generated.name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.symlink_to(session.creator.dest / link_to)
    with session:
        session.run()
    kept: Final = link_to == "original" and (
        generated.name == "CACHEDIR.TAG" or (generated.name == ".gitignore" and creator_name == "builtin")
    )
    assert path.is_symlink() is kept
    assert (target.read_bytes(), (session.creator.dest / "missing").exists()) == (b"original", False)


def test_venv_rejects_executable_directory_that_is_a_file(tmp_path: Path) -> None:
    session: Final = session_via_cli([str(tmp_path / "env"), "--creator", "venv", "--no-seed", "--activators="])
    session.creator.dest.mkdir()
    session.creator.bin_dir.write_bytes(b"file")
    with pytest.raises(NotADirectoryError, match="environment directory is not a real directory"):
        session.run()


@pytest.mark.skipif(not fs_supports_symlink(), reason="requires directory symlinks")
def test_venv_prepares_real_executable_directory_over_symlink(tmp_path: Path) -> None:
    session: Final = session_via_cli([str(tmp_path / "env"), "--creator", "venv", "--no-seed", "--activators="])
    session.creator.dest.mkdir()
    target: Final = session.creator.dest / "empty"
    target.mkdir()
    session.creator.bin_dir.symlink_to(target, target_is_directory=True)
    session.run()
    assert session.creator.bin_dir.resolve() == session.creator.bin_dir


@pytest.mark.skipif(not fs_supports_symlink(), reason="requires directory symlinks")
def test_venv_prepares_real_executable_directory_over_dangling_symlink(tmp_path: Path) -> None:
    session: Final = session_via_cli([str(tmp_path / "env"), "--creator", "venv", "--no-seed", "--activators="])
    session.creator.dest.mkdir()
    session.creator.bin_dir.symlink_to(session.creator.dest / "empty", target_is_directory=True)
    session.run()
    assert session.creator.bin_dir.resolve() == session.creator.bin_dir


@pytest.mark.skipif(not IS_WIN, reason="requires Windows junctions")
def test_venv_prepares_real_executable_directory_over_junction(tmp_path: Path) -> None:
    session: Final = session_via_cli([str(tmp_path / "env"), "--creator", "venv", "--no-seed", "--activators="])
    session.creator.dest.mkdir()
    target: Final = session.creator.dest / "empty"
    target.mkdir()
    subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(session.creator.bin_dir), str(target)],
        capture_output=True,
        check=True,
    )
    session.run()
    assert session.creator.bin_dir.resolve() == session.creator.bin_dir


def test_os_path_sep_not_allowed(tmp_path, capsys) -> None:
    target = str(tmp_path / f"a{os.pathsep}b")
    err = _non_success_exit_code(capsys, target)
    msg = (
        f"destination {target!r} must not contain the path separator ({os.pathsep})"
        f" as this would break the activation scripts"
    )
    assert msg in err, err


def _non_success_exit_code(capsys, target):
    with pytest.raises(SystemExit) as context:
        run_with_catch(args=[target])
    assert context.value.code != 0
    out, err = capsys.readouterr()
    assert "SystemExit: " in out
    return err


def test_resolved_destination_rejects_path_separator(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    parent: Final = tmp_path / f"parent{os.pathsep}directory"
    parent.mkdir()
    monkeypatch.chdir(parent)
    with pytest.raises(ArgumentTypeError, match="must not contain the path separator"):
        Creator.validate_dest("env")


@pytest.mark.skipif(not fs_supports_symlink(), reason="requires directory symlinks")
def test_symlinked_destination_rejects_path_separator(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    parent: Final = tmp_path / f"parent{os.pathsep}directory"
    parent.mkdir()
    (tmp_path / "link").symlink_to(parent, target_is_directory=True)
    monkeypatch.chdir(tmp_path)
    with pytest.raises(ArgumentTypeError, match="must not contain the path separator"):
        Creator.validate_dest("link/env")


_LEGACY_DESTINATIONS: Final[list[tuple[str, str]]] = [
    pytest.param("latin-1", "café", id="latin1"),
    pytest.param("koi8-r", "тест", id="koi8r"),
    pytest.param("gbk", "中文", id="gbk"),
    pytest.param("ascii", "café", id="unencodable"),
]


@pytest.fixture
def legacy_destination(tmp_path: Path, mocker: MockerFixture) -> Callable[[str, str], Path]:
    def _make(encoding: str, name: str) -> Path:
        dest = tmp_path / name / "env"
        encode = os.fsencode

        def legacy_encode(value: str | bytes | os.PathLike[str] | os.PathLike[bytes]) -> bytes:
            return str(value).encode(encoding) if value == str(dest) else encode(value)

        mocker.patch("os.fsencode", autospec=True, side_effect=legacy_encode)
        return dest

    return _make


@pytest.mark.skipif(IS_WIN, reason="Windows paths use Unicode APIs")
@pytest.mark.parametrize(("encoding", "name"), _LEGACY_DESTINATIONS)
def test_legacy_locale_rejects_selected_shell_activators(
    legacy_destination: Callable[[str, str], Path], encoding: str, name: str
) -> None:
    with pytest.raises(ValueError, match="activation scripts would point at a different directory"):
        session_via_cli([str(legacy_destination(encoding, name)), "--no-seed", "--activators", "bash"])


@pytest.mark.skipif(IS_WIN, reason="Windows paths use Unicode APIs")
@pytest.mark.parametrize("activators", [pytest.param("", id="none"), pytest.param("python", id="python")])
@pytest.mark.parametrize(("encoding", "name"), _LEGACY_DESTINATIONS)
def test_legacy_locale_allows_python_activator(
    legacy_destination: Callable[[str, str], Path], encoding: str, name: str, activators: str
) -> None:
    session = cli_run([str(legacy_destination(encoding, name)), "--no-seed", "--activators", activators])
    assert (session.creator.dest / "pyvenv.cfg").is_file()


@pytest.mark.skipif(IS_WIN, reason="Windows paths use Unicode APIs")
@pytest.mark.parametrize(("encoding", "name"), _LEGACY_DESTINATIONS)
def test_legacy_locale_skips_default_shell_activators(
    legacy_destination: Callable[[str, str], Path], encoding: str, name: str, caplog: pytest.LogCaptureFixture
) -> None:
    session = cli_run([str(legacy_destination(encoding, name)), "--no-seed"], setup_logging=False)
    assert [type(activator).__name__ for activator in session.activators] == ["PythonActivator"]
    assert "skipping shell activation scripts" in caplog.text


def test_destination_exists_file(tmp_path, capsys) -> None:
    target = tmp_path / "out"
    target.write_text("", encoding="utf-8")
    err = _non_success_exit_code(capsys, str(target))
    msg = f"the destination {target!s} already exists and is not a directory"
    assert msg in err, err


@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="requires FIFOs")
def test_destination_exists_fifo(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    target: Final[Path] = tmp_path / "fifo"
    os.mkfifo(target)
    with pytest.raises(SystemExit) as context:
        cli_run([str(target), "--no-seed"])
    assert (
        context.value.code,
        f"the destination {target} already exists and is not a directory" in capsys.readouterr().err,
    ) == (2, True)


def test_destination_exists_device(capsys: pytest.CaptureFixture[str]) -> None:
    target: Final[Path] = Path(os.devnull)
    with pytest.raises(SystemExit) as context:
        cli_run([str(target), "--no-seed"])
    assert (
        context.value.code,
        f"the destination {target} already exists and is not a directory" in capsys.readouterr().err,
    ) == (2, True)


def test_destination_inside_file(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (parent := tmp_path / "out").write_text("", encoding="utf-8")
    err: Final[str] = _non_success_exit_code(capsys, str(parent / "env"))
    assert f"is inside {parent.resolve()}, which is not a directory" in err, err


@pytest.mark.parametrize(
    ("args", "clear_env"),
    [
        pytest.param([""], "0", id="empty"),
        pytest.param(["", "--clear"], "0", id="empty-clear"),
        pytest.param([""], "1", id="empty-clear-environment"),
        pytest.param([" ", "--clear"], "0", id="space-clear"),
        pytest.param(["\t"], "0", id="tab"),
    ],
)
def test_blank_destination_leaves_working_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], args: list[str], clear_env: str
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "keep.txt").write_text("keep", encoding="utf-8")
    with pytest.raises(SystemExit) as context:
        cli_run([*args, "--no-seed"], env={**os.environ, "VIRTUALENV_CLEAR": clear_env})
    assert (
        context.value.code,
        [path.name for path in tmp_path.iterdir()],
        "must not be empty or whitespace; pass . to use the current directory" in capsys.readouterr().err,
    ) == (2, ["keep.txt"], True)


def test_dot_destination_is_working_directory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    session: Final = session_via_cli([".", "--clear", "--no-seed"])
    assert (session.creator.dest, session.creator.clear) == (tmp_path.resolve(), True)


@pytest.mark.skipif(sys.platform == "win32", reason="Windows only applies R/O to files")
@pytest.mark.skipif(hasattr(os, "geteuid") and os.geteuid() == 0, reason="root bypasses permission restrictions")
def test_destination_not_write_able(tmp_path, capsys) -> None:
    target = tmp_path
    prev_mod = target.stat().st_mode
    target.chmod(S_IREAD | S_IRGRP | S_IROTH)
    try:
        err = _non_success_exit_code(capsys, str(target))
        msg = f"the destination . is not write-able at {target!s}"
        assert msg in err, err
    finally:
        target.chmod(prev_mod)


def cleanup_sys_path(paths):
    # used only by this helper, so it stays out of the module imports
    from virtualenv.create.creator import HERE  # ruff:ignore[import-outside-top-level]

    paths = [p.resolve() for p in (Path(os.path.abspath(i)) for i in paths) if p.exists()]
    to_remove = [Path(HERE)]
    if os.environ.get("PYCHARM_HELPERS_DIR"):
        to_remove.extend((Path(os.environ["PYCHARM_HELPERS_DIR"]).parent, Path(os.path.expanduser("~")) / ".PyCharm"))
    return [i for i in paths if not any(str(i).startswith(str(t)) for t in to_remove)]


@pytest.fixture(scope="session")
def system(session_app_data):
    return get_env_debug_info(Path(_CURRENT.system_executable), DEBUG_SCRIPT, session_app_data, os.environ)


_CURRENT_CREATORS: Final[list[str]] = [
    i for i in CreatorSelector.for_interpreter(_CURRENT).key_to_class if i != "builtin"
]


@pytest.mark.skipif("venv" not in _CURRENT_CREATORS, reason="stdlib venv is unavailable")
@pytest.mark.parametrize(
    "boundary",
    [
        pytest.param(char, id=name)
        for name, char in (
            ("newline", "\n"),
            ("return", "\r"),
            ("vertical-tab", "\v"),
            ("form-feed", "\f"),
            ("file-separator", "\x1c"),
            ("group-separator", "\x1d"),
            ("record-separator", "\x1e"),
            ("next-line", "\x85"),
            ("line-separator", "\u2028"),
            ("paragraph-separator", "\u2029"),
        )
    ],
)
def test_venv_creator_rejects_line_boundary(tmp_path: Path, capsys: pytest.CaptureFixture[str], boundary: str) -> None:
    destination: Final = tmp_path / f"project{boundary}name"
    with pytest.raises(SystemExit) as context:
        cli_run([str(destination), "--creator", "venv", "--no-seed"])
    assert context.value.code == 2
    assert "must not contain a line boundary" in capsys.readouterr().err
    assert not list(tmp_path.iterdir())


@pytest.mark.skipif("venv" not in _CURRENT_CREATORS, reason="stdlib venv is unavailable")
def test_venv_creator_accepts_plain_destination(tmp_path: Path) -> None:
    session: Final = cli_run([str(tmp_path / "environment"), "--creator", "venv", "--no-seed"])
    assert (session.creator.dest / "pyvenv.cfg").is_file()


def _make_symlink(link: Path, stored: Path) -> None:
    link.symlink_to(stored, target_is_directory=True)


def _make_junction(link: Path, stored: Path) -> None:
    subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(stored)], capture_output=True, check=True)


@pytest.mark.parametrize(
    "make_link",
    [
        pytest.param(
            _make_symlink,
            id="symlink",
            marks=pytest.mark.skipif(not fs_supports_symlink(), reason="symlinks are unavailable"),
        ),
        pytest.param(
            _make_junction, id="junction", marks=pytest.mark.skipif(os.name != "nt", reason="Windows junctions")
        ),
    ],
)
@pytest.mark.parametrize(
    "creator_name",
    [
        pytest.param("builtin", id="builtin"),
        pytest.param(
            "venv",
            id="venv",
            marks=pytest.mark.skipif("venv" not in _CURRENT_CREATORS, reason="stdlib venv is unavailable"),
        ),
    ],
)
@pytest.mark.parametrize("folder", [pytest.param("bin_dir", id="executables"), pytest.param("purelib", id="packages")])
def test_creator_replaces_directory_links(
    tmp_path: Path, creator_name: str, folder: str, make_link: Callable[[Path, Path], None]
) -> None:
    session: Final = session_via_cli([str(tmp_path / "env"), "--creator", creator_name, "--no-seed"])
    session.creator.dest.mkdir()
    stored: Final = session.creator.dest / "stored"
    stored.mkdir()
    link: Final = session.creator.dest / getattr(session.creator, folder).relative_to(session.creator.dest).parts[0]
    make_link(link, stored)
    with session:
        session.run()
    assert (link.resolve(), session.creator.exe.is_file(), list(stored.iterdir())) == (link, True, [])


_CREATE_METHODS: Final[list[str]] = []


for key, meta in CreatorSelector.for_interpreter(_CURRENT).key_to_meta.items():
    if key in _CURRENT_CREATORS:
        if meta.can_copy:
            if key == "venv" and _CURRENT.implementation == "PyPy" and _CURRENT.pypy_version_info >= [7, 3, 13]:
                continue  # https://foss.heptapod.net/pypy/pypy/-/issues/4019
            _CREATE_METHODS.append((key, "copies"))
        if meta.can_symlink:
            _CREATE_METHODS.append((key, "symlinks"))


def _bin_exes(creator_key: str) -> tuple[str, ...]:
    if sys.platform == "win32":
        return ("python.exe",)
    exes = ("python", f"python{sys.version_info.major}", f"python{sys.version_info.major}.{sys.version_info.minor}")
    # for venv some repackaging does not includes the pythonx.y
    return exes[:-1] if creator_key == "venv" else exes


def _assert_isolated_sys_path(sys_path: list[Path], system_sys_path: list[Path]) -> None:
    global_sys_path = system_sys_path[-1]
    msg = "\n".join(str(j) for j in sys_path)
    msg = f"global sys path {global_sys_path!s} is in virtual environment sys path:\n{msg}"
    assert global_sys_path not in sys_path, msg


def _assert_system_site_sys_path(sys_path: list[Path], system_sys_path: list[Path]) -> None:
    assert sys_path[-1] == system_sys_path[-1], "\n".join(
        difflib.unified_diff([str(i) for i in sys_path], [str(i) for i in system_sys_path]),
    )


class _NoSeedCase(NamedTuple):
    creator: tuple[str, str]
    site_args: list[str]
    check_sys_path: Callable[[list[Path], list[Path]], None]


_NO_SEED_CASES: Final[list[pytest.ParameterSet]] = [
    pytest.param(_NoSeedCase(creator, site_args, check), id=f"{'-'.join(creator)}-{mode}")
    for creator in _CREATE_METHODS
    for site_args, check, mode in (
        ([], _assert_isolated_sys_path, "isolated"),
        (["--system-site-packages"], _assert_system_site_sys_path, "global"),
    )
]


@pytest.mark.graalpy
@pytest.mark.parametrize("case", _NO_SEED_CASES)
def test_create_no_seed(python, case: _NoSeedCase, system, coverage_env, special_name_dir) -> None:
    dest = special_name_dir
    creator_key, method = case.creator
    cmd = [
        "-v",
        "-v",
        "-p",
        str(python),
        str(dest),
        "--without-pip",
        "--activators",
        "",
        "--creator",
        creator_key,
        f"--{method}",
        *case.site_args,
    ]
    creator = cli_run(cmd).creator
    coverage_env()
    # pypy cleans up file descriptors periodically so our (many) subprocess calls impact file descriptor limits
    # force a close of these on system where the limit is low-ish (e.g. MacOS 256)
    gc.collect()
    purelib = creator.purelib
    patch_files = {purelib / f"{'_virtualenv'}.{i}" for i in ("py", "pyc", "pth")}
    patch_files.add(purelib / "__pycache__")
    content = set(creator.purelib.iterdir()) - patch_files
    assert not content, "\n".join(str(i) for i in content)
    assert creator.env_name == str(dest.name)
    debug = creator.debug
    assert "exception" not in debug, f"{debug.get('exception')}\n{debug.get('out')}\n{debug.get('err')}"
    sys_path = cleanup_sys_path(debug["sys"]["path"])
    system_sys_path = cleanup_sys_path(system["sys"]["path"])
    our_paths = set(sys_path) - set(system_sys_path)
    our_paths_repr = "\n".join(repr(i) for i in our_paths)

    # ensure we have at least one extra path added
    assert len(our_paths) >= 1, our_paths_repr
    # ensure all additional paths are related to the virtual environment
    for path in our_paths:
        msg = "\n".join(str(p) for p in system_sys_path)
        msg = f"\n{path!s}\ndoes not start with {dest!s}\nhas:\n{msg}"
        assert str(path).startswith(str(dest)), msg
    # ensure there's at least a site-packages folder as part of the virtual environment added
    assert any(p for p in our_paths if p.parts[-1] == "site-packages"), our_paths_repr

    case.check_sys_path(sys_path, system_sys_path)

    # the python executables in the bin directory are either files, absolute symlinks outside of the venv,
    # or relative symlinks inside of the venv
    bin_paths = [creator.bin_dir / exe for exe in _bin_exes(creator_key)]
    assert all(path.exists() for path in bin_paths), "\n".join(str(i) for i in creator.bin_dir.iterdir())
    absolute_links = [os.readlink(path) for path in bin_paths if path.is_symlink() and os.path.isabs(os.readlink(path))]
    assert not [link for link in absolute_links if link.startswith(str(creator.dest))]

    git_ignore = (dest / ".gitignore").read_text(encoding="utf-8")
    assert git_ignore.splitlines() == ["# created by virtualenv automatically", "*"]


@pytest.mark.skipif(
    not (IS_WIN and _CURRENT.implementation == "CPython"), reason="pythonw is a Windows CPython launcher"
)
def test_create_ships_pythonw(tmp_path: Path) -> None:
    creator: Final = cli_run([str(tmp_path / "env"), "--without-pip", "--activators", ""]).creator
    assert (creator.exe.parent / "pythonw.exe").read_bytes() != creator.exe.read_bytes()


def test_create_cachedir_tag(tmp_path) -> None:
    cachedir_tag_file = tmp_path / "CACHEDIR.TAG"
    cli_run([str(tmp_path), "--without-pip", "--activators", ""])

    expected = """
    Signature: 8a477f597d28d172789f06886806bc55
    # This file is a cache directory tag created by Python virtualenv.
    # For information about cache directory tags, see:
    #   https://bford.info/cachedir/
    """
    assert cachedir_tag_file.read_text(encoding="utf-8") == textwrap.dedent(expected).strip()


def test_create_cachedir_tag_exists(tmp_path: Path) -> None:
    cachedir_tag_file = tmp_path / "CACHEDIR.TAG"
    cachedir_tag_file.write_text("magic", encoding="utf-8")
    cli_run([str(tmp_path), "--without-pip", "--activators", ""])
    assert cachedir_tag_file.read_text(encoding="utf-8") == "magic"


def test_create_vcs_ignore_exists(tmp_path) -> None:
    git_ignore = tmp_path / ".gitignore"
    git_ignore.write_text("magic", encoding="utf-8")
    cli_run([str(tmp_path), "--without-pip", "--activators", ""])
    assert git_ignore.read_text(encoding="utf-8") == "magic"


def test_create_vcs_ignore_override(tmp_path) -> None:
    git_ignore = tmp_path / ".gitignore"
    cli_run([str(tmp_path), "--without-pip", "--no-vcs-ignore", "--activators", ""])
    assert not git_ignore.exists()


def test_create_vcs_ignore_exists_override(tmp_path) -> None:
    git_ignore = tmp_path / ".gitignore"
    git_ignore.write_text("magic", encoding="utf-8")
    cli_run([str(tmp_path), "--without-pip", "--no-vcs-ignore", "--activators", ""])
    assert git_ignore.read_text(encoding="utf-8") == "magic"


@pytest.mark.skipif(not _CURRENT.has_venv, reason="requires venv")
@pytest.mark.parametrize(
    ("site_args", "include_system_site"),
    [pytest.param([], "false", id="isolated"), pytest.param(["--system-site-packages"], "true", id="global")],
)
def test_venv_configuration_uses_selected_options(
    tmp_path: Path, site_args: list[str], include_system_site: str
) -> None:
    session: Final = cli_run([str(tmp_path / "env"), "--creator", "venv", "--no-seed", *site_args])
    session.creator.pyenv_cfg.path.write_text("vendor-marker = unused\n", encoding="utf-8")
    session.creator.set_pyenv_cfg()
    expected: Final = {"vendor-marker": None, "include-system-site-packages": include_system_site}
    assert {key: session.creator.pyenv_cfg.content.get(key) for key in expected} == expected


@pytest.mark.skipif(not IS_GRAALPY, reason="GraalPy records its launcher and base executable in pyvenv.cfg")
def test_venv_configuration_records_graalpy_executable(tmp_path: Path) -> None:
    session: Final = cli_run([str(tmp_path / "env"), "--creator", "venv", "--no-seed"])
    session.creator.set_pyenv_cfg()
    executable: Final = session.creator.interpreter.system_exe
    assert (
        session.creator.pyenv_cfg.content.get("venvlauncher_command"),
        session.creator.pyenv_cfg.content.get("base-executable"),
    ) == (executable, executable)


@pytest.mark.skipif(not _CURRENT.has_venv or not fs_supports_symlink(), reason="requires venv and symlinks")
@pytest.mark.skipif(
    is_mac_os_framework(_CURRENT) or is_macos_brew(_CURRENT) or (IS_GRAALPY and not IS_WIN),
    reason="stdlib creator requires symlinks on this runtime",
)
def test_venv_recreate_with_copied_interpreter(tmp_path: Path) -> None:
    args: Final = [str(tmp_path / "env"), "--creator", "venv", "--no-seed"]
    cli_run([*args, "--symlinks"])
    session: Final = cli_run([*args, "--copies"])
    assert (session.creator.exe.is_file(), session.creator.exe.resolve().parent) == (
        True,
        session.creator.bin_dir.resolve(),
    )


@pytest.mark.skipif(not _CURRENT.has_venv, reason="requires interpreter with venv")
def test_venv_subprocess_skips_local_venv_module(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "venv").mkdir()
    (tmp_path / "venv" / "__init__.py").write_text("raise SystemExit('imported from the working directory')", "utf-8")
    monkeypatch.chdir(tmp_path)
    session: Final = cli_run([
        "-p",
        str(_CURRENT.executable),
        str(tmp_path / "env"),
        "--without-pip",
        "--creator",
        "venv",
        "--no-periodic-update",
    ])
    assert (session.creator.dest / "pyvenv.cfg").is_file()


_HARD_LINKED_NAMES: Final[tuple[str, ...]] = (
    ("python.exe", "pythonw.exe") if IS_WIN else ("python", "python3", f"python3.{_CURRENT.version_info.minor}")
)


@pytest.mark.skipif(not _CURRENT.has_venv, reason="requires interpreter with venv")
@pytest.mark.parametrize(
    "mode",
    [
        pytest.param(
            "--copies",
            id="copies",
            marks=pytest.mark.skipif(
                is_mac_os_framework(_CURRENT) or is_macos_brew(_CURRENT) or (IS_GRAALPY and not IS_WIN),
                reason="stdlib creator requires symlinks on this runtime",
            ),
        ),
        pytest.param(
            "--symlinks",
            id="symlinks",
            marks=pytest.mark.skipif(not fs_supports_symlink(), reason="requires symlinks"),
        ),
    ],
)
def test_venv_replaces_hard_linked_files(tmp_path: Path, mode: str) -> None:
    session: Final = session_via_cli([str(tmp_path / "env"), "--creator", "venv", "--no-seed", "--activators=", mode])
    session.creator.bin_dir.mkdir(parents=True)
    planted: Final = [
        session.creator.dest / "pyvenv.cfg",
        *(session.creator.bin_dir / name for name in _HARD_LINKED_NAMES),
    ]
    for path in planted:
        (tmp_path / f"{path.name}.original").write_bytes(b"original")
        os.link(tmp_path / f"{path.name}.original", path)
    session.run()
    assert [((tmp_path / f"{path.name}.original").read_bytes(), path.lstat().st_nlink) for path in planted] == [
        (b"original", 1)
    ] * len(planted)


@pytest.mark.skipif(not _CURRENT.has_venv, reason="requires interpreter with venv")
@pytest.mark.skipif(hasattr(os, "geteuid") and os.geteuid() == 0, reason="root bypasses permission restrictions")
def test_venv_fails_not_inline(tmp_path, capsys, mocker) -> None:
    def _session_via_cli(args, options=None, setup_logging=True, env=None):
        session = session_via_cli(args, options, setup_logging, env)
        assert session.creator.can_be_inline is False
        return session

    mocker.patch("virtualenv.run.cli.session_via_cli", side_effect=_session_via_cli, autospec=True)
    before = tmp_path.stat().st_mode
    cfg_path = tmp_path / "pyvenv.cfg"
    cfg_path.write_text("", encoding="utf-8")
    cfg = str(cfg_path)
    try:
        os.chmod(cfg, stat.S_IREAD | stat.S_IRGRP | stat.S_IROTH)
        cmd = ["-p", str(_CURRENT.executable), str(tmp_path), "--without-pip", "--creator", "venv"]
        with pytest.raises(SystemExit) as context:
            run(cmd)
        assert context.value.code != 0
    finally:
        os.chmod(cfg, before)
    out, err = capsys.readouterr()
    assert "subprocess call failed for" in out, out
    assert "Error:" in err, err


@pytest.mark.parametrize(
    ("creator", "clear_args"),
    [
        pytest.param(creator, clear_args, id=f"{creator}-{clear_id}", marks=marks)
        for creator in _CURRENT_CREATORS
        for clear_args, clear_id, marks in (
            (["--clear"], "clear", []),
            ([], "no_clear", [pytest.mark.skipif(creator == "venv", reason="venv without clear might fail")]),
        )
    ],
)
def test_create_clear_resets(tmp_path, creator: str, clear_args: list[str], caplog) -> None:
    caplog.set_level(logging.DEBUG)
    marker = tmp_path / "magic"
    cmd = [str(tmp_path), "--seeder", "app-data", "--without-pip", "--creator", creator, "-vvv"]
    cli_run(cmd)

    marker.write_text("", encoding="utf-8")  # if we a marker file this should be gone on a clear run, remain otherwise
    assert marker.exists()

    cli_run([*cmd, *clear_args])
    assert marker.exists() is not bool(clear_args)


@pytest.mark.parametrize("creator", _CURRENT_CREATORS)
@pytest.mark.parametrize("prompt", ["magic", "."])
def test_prompt_set(tmp_path: Path, creator: str, prompt: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    cmd = [str(tmp_path / "env"), "--seeder", "app-data", "--without-pip", "--creator", creator, "--prompt", prompt]
    cfg = PyEnvCfg.from_file(cli_run(cmd).creator.pyenv_cfg.path)
    # pathlib normalizes "." away, so the default prompt is the folder name
    expected = (tmp_path / prompt).name
    assert "prompt" in cfg, list(cfg.content.keys())
    assert cfg["prompt"] == expected


# the tests below only read the environment, so each creator builds it once per module
@pytest.fixture(scope="module")
def default_env(request: pytest.FixtureRequest, tmp_path_factory: pytest.TempPathFactory) -> Session:
    dest = tmp_path_factory.mktemp(f"default-{request.param}")
    return cli_run([
        str(dest),
        "--seeder",
        "app-data",
        "--without-pip",
        "--creator",
        request.param,
        "--no-periodic-update",
    ])


@pytest.mark.parametrize("default_env", _CURRENT_CREATORS, indirect=True)
def test_prompt_not_set_by_default(default_env: Session) -> None:
    assert "prompt" not in PyEnvCfg.from_file(default_env.creator.pyenv_cfg.path)


@pytest.mark.parametrize("default_env", _CURRENT_CREATORS, indirect=True)
def test_version_keys_in_pyenv_cfg(default_env: Session) -> None:
    cfg = PyEnvCfg.from_file(default_env.creator.pyenv_cfg.path)
    version_info = default_env.creator.interpreter.version_info
    assert cfg["python-version"] == f"{version_info.major}.{version_info.minor}"
    assert "version" in cfg
    parts = cfg["version"].split(".")
    assert len(parts) == 3
    assert all(p.isdigit() for p in parts)


@pytest.mark.parametrize("default_env", [c for c in _CURRENT_CREATORS if c != "venv"], indirect=True)
def test_executable_and_command_keys(default_env: Session) -> None:
    cfg = PyEnvCfg.from_file(default_env.creator.pyenv_cfg.path)
    assert "executable" in cfg
    assert Path(cfg["executable"]).exists()
    assert "command" in cfg
    assert "virtualenv" in cfg["command"]


_INCLUDE_DIR_NAME: Final[str] = "Include" if IS_WIN else "include"


@pytest.mark.parametrize("default_env", [c for c in _CURRENT_CREATORS if c != "venv"], indirect=True)
def test_include_dir_created(default_env: Session) -> None:
    assert (default_env.creator.dest / _INCLUDE_DIR_NAME).is_dir()


@pytest.mark.parametrize("default_env", _CURRENT_CREATORS, indirect=True)
def test_home_path_is_exe_parent(default_env: Session) -> None:
    cfg = PyEnvCfg.from_file(default_env.creator.pyenv_cfg.path)

    # Cannot assume "home" path is a specific value as path resolution may change
    # between versions (symlinks, framework paths, etc) but we can check that a
    # python executable is present from the configured path per PEP 405
    assert any(os.path.exists(os.path.join(cfg["home"], exe)) for exe in _bin_exes("builtin"))


@pytest.mark.skipif(IS_WIN or not fs_supports_symlink(), reason="requires POSIX interpreter aliases")
@pytest.mark.parametrize(
    "mode",
    [
        pytest.param(
            "--copies",
            id="copy",
            marks=pytest.mark.skipif(
                is_macos_brew(_CURRENT) or is_mac_os_framework(_CURRENT),
                reason="Homebrew and framework builds require symlinks",
            ),
        ),
        pytest.param("--symlinks", id="symlink"),
    ],
)
def test_recreate_environment_with_dangling_alias(tmp_path: Path, mode: str) -> None:
    destination: Final[Path] = tmp_path / "venv"
    cli_run([str(destination), "--creator", "builtin", "--no-seed", "--symlinks"])
    alias: Final[Path] = destination / "bin" / f"python{sys.version_info.major}"
    alias.unlink()
    outside: Final[Path] = tmp_path / "removed-python"
    alias.symlink_to(outside)

    cli_run([str(destination), "--creator", "builtin", "--no-seed", mode])

    assert (alias.is_symlink(), alias.is_file(), outside.exists()) == (mode == "--symlinks", True, False)


@pytest.mark.skipif(not IS_WIN, reason="Windows refuses to delete read-only files")
def test_recreate_environment_over_read_only_executables(tmp_path: Path) -> None:
    args: Final = [str(tmp_path / "venv"), "--creator", "builtin", "--no-seed", "--activators=", "--copies"]
    executables: Final = list(cli_run(args).creator.bin_dir.iterdir())
    for path in executables:
        path.chmod(S_IREAD)

    cli_run(args)

    assert [path.name for path in executables if not os.access(path, os.W_OK)] == []


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX only")
@pytest.mark.skipif(
    bool(_CURRENT.sysconfig_vars.get("PYTHONFRAMEWORK")),
    reason="framework builds self-locate via dyld and keep the recorded path",
)
@pytest.mark.usefixtures("temp_app_data")
def test_home_resolves_executable_only_symlink(tmp_path: Path) -> None:
    # An executable-only symlink must not be recorded as home / base-executable (issue #3157).
    system_exe = _CURRENT.system_executable
    assert system_exe is not None
    link = tmp_path / "symdir" / "python3"
    link.parent.mkdir()
    link.symlink_to(system_exe)

    result = cli_run(["-p", str(link), str(tmp_path / "env"), "--seeder", "app-data", "--without-pip"])
    cfg = PyEnvCfg.from_file(result.creator.pyenv_cfg.path)

    assert Path(cfg["home"]) != link.parent
    assert os.path.samefile(cfg["base-executable"], system_exe)
    assert Path(cfg["home"]) == Path(cfg["base-executable"]).parent


@pytest.mark.usefixtures("temp_app_data")
def test_create_parallel(tmp_path) -> None:
    def create(count) -> None:
        subprocess.check_call(
            [sys.executable, "-m", "virtualenv", "-vvv", str(tmp_path / f"venv{count}"), "--without-pip"],
        )

    threads = [Thread(target=create, args=(i,)) for i in range(1, 4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()


def test_creator_input_passed_is_abs(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    result = Creator.validate_dest("venv")
    assert str(result) == str(tmp_path / "venv")


@pytest.mark.skipif(os.altsep is None, reason="OS does not have an altsep")
def test_creator_replaces_altsep_in_dest(tmp_path) -> None:
    dest = str(tmp_path / "venv{}foobar")
    result = Creator.validate_dest(dest.format(os.altsep))
    assert str(result) == dest.format(os.sep)


_MAX_SHEBANG_LENGTH: Final[int] = 512 if sys.platform == "darwin" else 127


@pytest.mark.usefixtures("current_fastest")
def test_create_long_path(tmp_path) -> None:
    # filenames can be at most 255 long on macOS, so split to two levels
    count = _MAX_SHEBANG_LENGTH - len(str(tmp_path))
    folder = tmp_path / ("a" * (count // 2)) / ("b" * (count // 2)) / "c"
    folder.mkdir(parents=True)

    subprocess.check_call([str(cli_run([str(folder), "--without-pip"]).creator.exe), "--version"])


@pytest.mark.slow
@pytest.mark.parametrize(
    "creator", sorted(set(CreatorSelector.for_interpreter(PythonInfo.current_system()).key_to_class) - {"builtin"})
)
@pytest.mark.usefixtures("session_app_data")
def test_create_distutils_cfg(creator, tmp_path, monkeypatch) -> None:
    result = cli_run(
        [
            str(tmp_path / "venv"),
            "--activators",
            "",
            "--creator",
            creator,
            "--setuptools",
            "bundle",
        ],
    )

    app = Path(__file__).parent / "console_app"
    dest = tmp_path / "console_app"
    shutil.copytree(str(app), str(dest))

    setup_cfg = dest / "setup.cfg"
    conf = dedent(
        f"""
            [install]
            prefix={tmp_path}{os.sep}prefix
            install_purelib={tmp_path}{os.sep}purelib
            install_platlib={tmp_path}{os.sep}platlib
            install_headers={tmp_path}{os.sep}headers
            install_scripts={tmp_path}{os.sep}scripts
            install_data={tmp_path}{os.sep}data
            """,
    )
    setup_cfg.write_text(setup_cfg.read_text(encoding="utf-8") + conf, encoding="utf-8")

    monkeypatch.chdir(dest)  # distutils will read the setup.cfg from the cwd, so change to that

    install_demo_cmd = [
        str(result.creator.script("pip")),
        "--disable-pip-version-check",
        "install",
        str(dest),
        "-vv",
    ]
    subprocess.check_call(install_demo_cmd)

    magic = result.creator.script("magic")  # console scripts are created in the right location
    assert magic.exists()

    package_folder = result.creator.purelib / "demo"  # prefix is set to the virtualenv prefix for install
    assert package_folder.exists(), list_files(str(tmp_path))


def list_files(path):
    result = ""
    for root, _, files in os.walk(path):
        level = root.replace(path, "").count(os.sep)
        result += f"{(' ' * 4 * level)}{os.path.basename(root)}/\n"
        sub = " " * 4 * (level + 1)
        for name in files:
            result += f"{sub}{name}\n"
    return result


def test_install_patch_skipped_on_py310(tmp_path, mocker) -> None:
    interpreter = mocker.create_autospec(PythonInfo, instance=True, version_info=(3, 10, 0))
    creator = mocker.create_autospec(ViaGlobalRefApi, instance=True, purelib=tmp_path, interpreter=interpreter)
    creator.env_patch_text.return_value = "import _virtualenv"
    ViaGlobalRefApi.install_patch(creator)
    assert not (tmp_path / "_virtualenv.pth").exists()
    assert not (tmp_path / "_virtualenv.py").exists()
    creator.env_patch_text.assert_not_called()


def test_install_patch_written_on_py39(tmp_path, mocker) -> None:
    interpreter = mocker.create_autospec(PythonInfo, instance=True, version_info=(3, 9, 21))
    creator = mocker.create_autospec(ViaGlobalRefApi, instance=True, purelib=tmp_path, interpreter=interpreter)
    creator.env_patch_text.return_value = "import _virtualenv"
    ViaGlobalRefApi.install_patch(creator)
    assert (tmp_path / "_virtualenv.pth").read_text(encoding="utf-8") == "import _virtualenv"
    assert (tmp_path / "_virtualenv.py").read_text(encoding="utf-8") == "import _virtualenv"


@pytest.mark.skipif(is_macos_brew(_CURRENT), reason="no copy on brew")
@pytest.mark.skip(reason="https://github.com/pypa/setuptools/issues/4640")
def test_zip_importer_can_import_setuptools(tmp_path) -> None:
    # We're patching the loaders so might fail on r/o loaders, such as zipimporter on CPython<3.8
    result = cli_run(
        [str(tmp_path / "venv"), "--activators", "", "--no-pip", "--no-wheel", "--copies", "--setuptools", "bundle"],
    )
    zip_path = tmp_path / "site-packages.zip"
    with zipfile.ZipFile(str(zip_path), "w", zipfile.ZIP_DEFLATED) as zip_handler:
        lib = str(result.creator.purelib)
        for root, _, files in os.walk(lib):
            base = root[len(lib) :].lstrip(os.pathsep)
            for file in (name for name in files if not name.startswith("_virtualenv")):
                zip_handler.write(filename=os.path.join(root, file), arcname=os.path.join(base, file))
    unwanted: Final = [
        folder for folder in result.creator.purelib.iterdir() if not folder.name.startswith("_virtualenv")
    ]
    for folder in (path for path in unwanted if path.is_dir()):
        shutil.rmtree(str(folder), ignore_errors=True)
    for file in (path for path in unwanted if not path.is_dir()):
        file.unlink()
    env = os.environ.copy()
    env["PYTHONPATH"] = str(zip_path)
    subprocess.check_call([str(result.creator.exe), "-c", "from setuptools.dist import Distribution"], env=env)


# verify that python in created virtualenv does not preimport threading.
# https://github.com/pypa/virtualenv/issues/1895
#
# coverage is disabled, because when coverage is active, it imports threading in default mode.
@pytest.mark.xfail(
    IS_PYPY and sys.platform.startswith("darwin"),
    reason="https://foss.heptapod.net/pypy/pypy/-/issues/3269",
)
@pytest.mark.usefixtures("_no_coverage")
def test_no_preimport_threading(tmp_path) -> None:
    session = cli_run([str(tmp_path)])
    out = subprocess.check_output(
        [str(session.creator.exe), "-c", r"import sys; print('\n'.join(sorted(sys.modules)))"],
        text=True,
        encoding="utf-8",
    )
    imported = set(out.splitlines())
    assert "threading" not in imported


# verify that .pth files in site-packages/ are always processed even if $PYTHONPATH points to it.
def test_pth_in_site_vs_python_path(tmp_path) -> None:
    session = cli_run([str(tmp_path), "--without-pip"])
    site_packages = session.creator.purelib
    # install test.pth that sets sys.testpth='ok'
    (session.creator.purelib / "test.pth").write_text('import sys; sys.testpth="ok"\n', encoding="utf-8")
    # verify that test.pth is activated when interpreter is run
    out = subprocess.check_output(
        [str(session.creator.exe), "-c", r"import sys; print(sys.testpth)"],
        text=True,
        encoding="utf-8",
    )
    assert out == "ok\n"
    # same with $PYTHONPATH pointing to site_packages
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join(filter(None, [str(site_packages), os.environ.get("PYTHONPATH", "")]))
    out = subprocess.check_output(
        [str(session.creator.exe), "-c", r"import sys; print(sys.testpth)"],
        text=True,
        env=env,
        encoding="utf-8",
    )
    assert out == "ok\n"


_CASE_FOLD: Final[Callable[[str], str]] = str if fs_is_case_sensitive() else str.lower


def test_getsitepackages_system_site(tmp_path) -> None:
    # Test without --system-site-packages
    session = cli_run([str(tmp_path), "--without-pip"])

    system_site_packages = get_expected_system_site_packages(session)

    out = subprocess.check_output(
        [str(session.creator.exe), "-c", r"import site; print(site.getsitepackages())"],
        text=True,
        encoding="utf-8",
    )
    site_packages = ast.literal_eval(out)

    for system_site_package in system_site_packages:
        assert system_site_package not in site_packages

    env_site_packages = [_CASE_FOLD(str(session.creator.purelib)), _CASE_FOLD(str(session.creator.platlib))]
    site_packages = [_CASE_FOLD(i) for i in site_packages]
    for env_site_package in env_site_packages:
        assert env_site_package in site_packages

    # Test with --system-site-packages
    session = cli_run([str(tmp_path), "--system-site-packages", "--without-pip"])

    system_site_packages = [str(Path(i).resolve()) for i in get_expected_system_site_packages(session)]

    out = subprocess.check_output(
        [str(session.creator.exe), "-c", r"import site; print(site.getsitepackages())"],
        text=True,
        encoding="utf-8",
    )
    site_packages = [str(Path(i).resolve()) for i in ast.literal_eval(out)]

    for system_site_package in system_site_packages:
        assert system_site_package in site_packages


def get_expected_system_site_packages(session):
    base_prefix = session.creator.pyenv_cfg["base-prefix"]
    base_exec_prefix = session.creator.pyenv_cfg["base-exec-prefix"]
    old_prefixes = site.PREFIXES
    site.PREFIXES = [base_prefix, base_exec_prefix]
    system_site_packages = site.getsitepackages()
    site.PREFIXES = old_prefixes

    return system_site_packages


def test_debug_bad_virtualenv(tmp_path) -> None:
    result = cli_run([str(tmp_path), "--without-pip"])
    # if the site.py is removed/altered the debug should fail as no one is around to fix the paths
    cust = result.creator.purelib / "_a.pth"
    cust.write_text(
        'import sys; sys.stdout.write("std-out"); sys.stderr.write("std-err"); raise SystemExit(1)',
        encoding="utf-8",
    )
    debug_info = result.creator.debug
    assert debug_info["returncode"] == 1
    assert "std-err" in debug_info["err"]
    assert "std-out" in debug_info["out"]
    assert debug_info["exception"]


def test_debug_ignores_python_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    extra: Final = tmp_path / "extra"
    extra.mkdir()
    monkeypatch.setenv("PYTHONPATH", str(extra))
    session: Final = cli_run([str(tmp_path / "venv"), "--without-pip", "--activators", ""])
    assert str(extra) not in session.creator.debug["sys"]["path"]


def _assert_python_path_applied(
    base: list[str], extra_all: list[str], python_paths: list[str], case_sensitive: bool
) -> None:
    assert not extra_all[0]  # the cwd is always injected at start as ''
    extra_all = extra_all[1:]
    assert not base[0]
    base = base[1:]

    assert not (set(base) - set(extra_all))  # all base paths are present
    abs_python_paths = list(OrderedDict((os.path.abspath(str(i)), None) for i in python_paths).keys())
    abs_python_paths = [i if case_sensitive else i.lower() for i in abs_python_paths]

    extra_as_python_path = extra_all[: len(abs_python_paths)]
    assert abs_python_paths == extra_as_python_path  # python paths are there at the start

    non_python_path = extra_all[len(abs_python_paths) :]
    assert non_python_path == [i for i in base if i not in extra_as_python_path]


def _assert_python_path_ignored(
    base: list[str], extra_all: list[str], _python_paths: list[str], _case_sensitive: bool
) -> None:
    assert base == extra_all


@pytest.mark.graalpy
@pytest.mark.parametrize(
    ("flag", "check"),
    [
        pytest.param(None, _assert_python_path_applied, id="on"),
        pytest.param("-E", _assert_python_path_ignored, id="off"),
    ],
)
def test_python_path(
    monkeypatch,
    tmp_path,
    flag: str | None,
    check: Callable[[list[str], list[str], list[str], bool], None],
) -> None:
    result = cli_run([str(tmp_path), "--without-pip", "--activators", ""])
    monkeypatch.chdir(tmp_path)
    case_sensitive = fs_is_case_sensitive()

    def _get_sys_path(flag=None):
        cmd = [str(result.creator.exe)]
        if flag:
            cmd.append(flag)
        cmd.extend(["-c", "import json; import sys; print(json.dumps(sys.path))"])
        return [i if case_sensitive else i.lower() for i in json.loads(subprocess.check_output(cmd, encoding="utf-8"))]

    monkeypatch.delenv("PYTHONPATH", raising=False)
    base = _get_sys_path()

    # note the value result.creator.interpreter.system_stdlib cannot be set, as that would disable our custom site.py
    python_paths = [
        str(Path(result.creator.interpreter.prefix)),
        str(Path(result.creator.interpreter.system_stdlib) / "b"),
        str(result.creator.purelib / "a"),
        str(result.creator.purelib),
        str(result.creator.bin_dir),
        str(tmp_path / "base"),
        f"{tmp_path / 'base_sep'!s}{os.sep}",
        "name",
        f"name{os.sep}",
        f"{tmp_path.parent}{f'{tmp_path.name}_suffix'}",
        ".",
        "..",
        "",
    ]
    monkeypatch.setenv("PYTHONPATH", os.pathsep.join(python_paths))

    check(base, _get_sys_path(flag), python_paths, case_sensitive)


# Make sure that the venv creator works on systems where vendor-delivered files
# (specifically venv scripts delivered with Python itself) are not writable.
#
# https://github.com/pypa/virtualenv/issues/2419
@pytest.mark.skipif("venv" not in _CURRENT_CREATORS, reason="test needs venv creator")
def test_venv_creator_without_write_perms(tmp_path, mocker) -> None:
    # imported with the test that patches Session._create
    from virtualenv.run.session import Session  # ruff:ignore[import-outside-top-level]

    # the test patches the private _create to simulate a read-only target
    prev = Session._create  # ruff:ignore[private-member-access]

    def func(self) -> None:
        prev(self)
        for script in (self.creator.dest / "bin").glob("*ctivate*"):
            script.chmod(stat.S_IREAD | stat.S_IRGRP | stat.S_IROTH)

    mocker.patch("virtualenv.run.session.Session._create", side_effect=func, autospec=True)

    cli_run([str(tmp_path), "--seeder", "app-data", "--without-pip", "--creator", "venv"])


@pytest.mark.skipif(is_macos_brew(_CURRENT), reason="brew python on darwin may not support copies, tested separately")
def test_fallback_to_copies_if_symlink_unsupported(tmp_path, python, mocker) -> None:
    # Test that creating a virtual environment falls back to copies when filesystem has no symlink support.
    # Given a filesystem that does not support symlinks
    mocker.patch("virtualenv.create.via_global_ref.api.fs_supports_symlink", return_value=False, autospec=True)

    # When creating a virtual environment (no method specified)
    cmd = [
        "-v",
        "-p",
        str(python),
        str(tmp_path),
        "--without-pip",
        "--activators",
        "",
    ]
    result = cli_run(cmd)

    # Then the creation should succeed and the creator should report it used copies
    assert result.creator is not None
    assert result.creator.symlinks is False


def _create_without_symlink_or_copy(tmp_path: Path, python: Path) -> str:
    with pytest.raises(RuntimeError) as excinfo:
        cli_run(["-p", str(python), str(tmp_path), "--without-pip"])
    assert "neither symlink or copy method supported" in str(excinfo.value)
    assert "symlink: the filesystem does not supports symlink" in str(excinfo.value)
    return str(excinfo.value)


def _patch_copy_unsupported(mocker: MockerFixture) -> None:
    original_init = api.ViaGlobalRefMeta.__init__

    def new_init(self, *args, **kwargs) -> None:
        original_init(self, *args, **kwargs)
        self.copy_error = "copying is not supported"

    mocker.patch("virtualenv.create.via_global_ref.api.ViaGlobalRefMeta.__init__", new=new_init)


@pytest.mark.skipif(not is_macos_brew(_CURRENT), reason="requires brew python on darwin")
def test_fail_gracefully_brew_python_reports_copy_disabled(tmp_path, python, mocker) -> None:
    mocker.patch("virtualenv.create.via_global_ref.api.fs_supports_symlink", return_value=False, autospec=True)
    message = _create_without_symlink_or_copy(tmp_path, python)
    assert "copy: Brew disables copy creation" in message


@pytest.mark.skipif(
    is_macos_brew(_CURRENT) or is_mac_os_framework(_CURRENT),
    reason="brew and framework builds report their own copy error",
)
def test_fail_gracefully_if_no_method_supported(tmp_path, python, mocker) -> None:
    mocker.patch("virtualenv.create.via_global_ref.api.fs_supports_symlink", return_value=False, autospec=True)
    _patch_copy_unsupported(mocker)
    message = _create_without_symlink_or_copy(tmp_path, python)
    assert "copy: copying is not supported" in message


@pytest.mark.skipif(not is_mac_os_framework(_CURRENT), reason="requires macOS framework python")
def test_fail_gracefully_framework_python_reports_copy_unsupported(tmp_path, python, mocker) -> None:
    mocker.patch("virtualenv.create.via_global_ref.api.fs_supports_symlink", return_value=False, autospec=True)
    _patch_copy_unsupported(mocker)
    message = _create_without_symlink_or_copy(tmp_path, python)
    assert "copy: macOS framework builds do not support copy-based virtual environments" in message


def test_pyenv_cfg_preserves_symlinks(tmp_path) -> None:
    # Test that PyEnvCfg.write() preserves symlinks and doesn't resolve them (issue #2770).
    # Create a real directory and a symlink to it
    real_dir = tmp_path / "real_directory"
    real_dir.mkdir()
    (real_dir / "some_file.txt").write_text("test", encoding="utf-8")

    symlink_dir = tmp_path / "symlink_directory"
    try:
        symlink_dir.symlink_to(real_dir, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("Symlinks not supported on this platform")

    cfg_path = tmp_path / "pyvenv.cfg"
    cfg = PyEnvCfg(OrderedDict(), cfg_path)

    symlink_path = str(symlink_dir / "some_file.txt")
    cfg["home"] = symlink_path
    cfg.write()

    written_content = cfg_path.read_text(encoding="utf-8")
    expected_abspath = os.path.abspath(symlink_path)
    expected_realpath = os.path.realpath(symlink_path)

    assert f"home = {expected_abspath}" in written_content
    assert expected_abspath != expected_realpath, "Test setup error: paths should differ for symlinks"


@pytest.mark.parametrize(
    ("key", "value", "normalize"),
    [
        pytest.param("home", "base", os.path.abspath, id="home"),
        pytest.param("python-version", "3.14", str, id="python-version"),
        pytest.param("version", "3.14.6", str, id="version"),
        pytest.param("implementation", "CPython", str, id="implementation"),
        pytest.param("include-system-site-packages", "true", str, id="include-system-site-packages"),
    ],
)
def test_pyenv_cfg_value_naming_entry_in_cwd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, key: str, value: str, normalize: Callable[[str], str]
) -> None:
    (tmp_path / value).mkdir()
    monkeypatch.chdir(tmp_path)
    cfg = PyEnvCfg(OrderedDict({key: value}), tmp_path / "pyvenv.cfg")

    cfg.write()

    assert PyEnvCfg.from_file(cfg.path).content == {key: normalize(value)}


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        pytest.param("\n\nhome = /a\n", {"home": "/a"}, id="blank-line"),
        pytest.param("# home = /b\nhome = /a\n", {"home": "/a"}, id="comment"),
        pytest.param("  # home = /b\nhome = /a\n", {"home": "/a"}, id="indented-comment"),
        pytest.param("no-separator\nhome = /a\n", {"home": "/a"}, id="no-separator"),
        pytest.param('home = /a\nprompt = "a b"\n', {"home": "/a", "prompt": "a b"}, id="quoted-value"),
    ],
)
def test_pyenv_cfg_from_folder_skips_non_entries(tmp_path: Path, text: str, expected: dict[str, str]) -> None:
    (tmp_path / "pyvenv.cfg").write_text(text, encoding="utf-8")

    assert PyEnvCfg.from_folder(tmp_path).content == expected


@pytest.mark.parametrize(
    "operation",
    [pytest.param("read", id="read"), pytest.param("write", id="write"), pytest.param("refresh", id="refresh")],
)
def test_pyenv_cfg_rejects_non_file_path(tmp_path: Path, operation: str) -> None:
    config: Final = PyEnvCfg(OrderedDict(), tmp_path)
    action: Final = {
        "read": partial(PyEnvCfg.from_file, tmp_path),
        "write": config.write,
        "refresh": config.refresh,
    }[operation]
    with pytest.raises(ValueError, match="configuration path is not a regular file"):
        action()


@pytest.fixture
def latin1_locale() -> str:
    locales: Final = subprocess.check_output(["locale", "-a"], text=True, encoding="utf-8").splitlines()
    names: Final = [name for name in locales if name.lower() == "aa_dj.iso88591"]
    if not names:
        pytest.skip("Latin-1 locale is unavailable")
    return names[0]


@pytest.mark.skipif(IS_WIN, reason="POSIX locales")
@pytest.mark.usefixtures("_no_coverage")
def test_default_activators_allow_legacy_locale(tmp_path: Path, latin1_locale: str) -> None:
    parent: Final = os.fsencode(tmp_path) + b"/calf\xe9"
    os.mkdir(parent)
    result: Final = subprocess.run(
        [sys.executable, "-m", "virtualenv", "env", "--no-seed"],
        cwd=parent,
        env={**os.environ, "LC_ALL": latin1_locale, "PYTHONUTF8": "0", "PYTHONCOERCECLOCALE": "0"},
        capture_output=True,
        check=True,
    )
    assert b"skipping shell activation scripts" in result.stdout + result.stderr
    assert os.path.isfile(parent + b"/env/pyvenv.cfg")
    assert not os.path.exists(parent + b"/env/bin/activate")


def test_pyenv_cfg_encoding_failure_preserves_file(tmp_path: Path) -> None:
    config: Final = PyEnvCfg(OrderedDict({"prompt": "\udcff"}), tmp_path / "pyvenv.cfg")
    config.path.write_bytes(b"home = original\n")
    with pytest.raises(UnicodeEncodeError):
        config.write()
    assert config.path.read_bytes() == b"home = original\n"


def test_pyenv_cfg_write_logs_escaped_values(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG)
    PyEnvCfg(OrderedDict({"prompt": "a\x1bb"}), tmp_path / "pyvenv.cfg").write()
    assert "\t'prompt = \"a\\x1bb\"'" in caplog.text


@pytest.mark.skipif(not _CURRENT.has_venv, reason="requires interpreter with venv")
@pytest.mark.skipif(_CURRENT.implementation != "CPython", reason="only CPython rejects an invalid PYTHONHOME")
def test_venv_subprocess_respects_pythonhome(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    session = session_via_cli(["-p", str(_CURRENT.executable), str(tmp_path / "env"), "--no-seed", "--creator", "venv"])
    monkeypatch.setenv("PYTHONHOME", str(tmp_path / "missing-home"))
    with pytest.raises(ProcessCallFailedError):
        session.run()
