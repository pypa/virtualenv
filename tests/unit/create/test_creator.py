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
from itertools import product
from pathlib import Path
from stat import S_IREAD, S_IRGRP, S_IROTH
from textwrap import dedent
from threading import Thread
from typing import TYPE_CHECKING, Final

import pytest
from python_discovery import PythonInfo

from virtualenv.__main__ import run, run_with_catch
from virtualenv.create.creator import DEBUG_SCRIPT, Creator, get_env_debug_info
from virtualenv.create.pyenv_cfg import PyEnvCfg
from virtualenv.create.via_global_ref import api
from virtualenv.create.via_global_ref.builtin.cpython.common import is_mac_os_framework, is_macos_brew
from virtualenv.info import IS_GRAALPY, IS_PYPY, IS_WIN, fs_is_case_sensitive, fs_supports_symlink
from virtualenv.run import cli_run, session_via_cli
from virtualenv.run.plugin.creators import CreatorSelector
from virtualenv.util.error import ProcessCallFailedError

if TYPE_CHECKING:
    from collections.abc import Callable

    from pytest_mock import MockerFixture

    from virtualenv.run.session import Session

CURRENT = PythonInfo.current_system()


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
@pytest.mark.parametrize("parent_link", [pytest.param(False, id="direct"), pytest.param(True, id="linked-parent")])
def test_clear_direct_destination(tmp_path: Path, parent_link: bool) -> None:
    target: Final = tmp_path / "target"
    target.mkdir()
    marker: Final = target / "old.txt"
    marker.write_text("old", encoding="utf-8")
    link: Final = tmp_path / "parent"
    link.symlink_to(tmp_path, target_is_directory=True)
    session: Final = cli_run([str(link / "target" if parent_link else target), "--clear", "--no-seed"])
    assert (session.creator.dest, marker.exists(), (target / "pyvenv.cfg").is_file()) == (target.resolve(), False, True)


@pytest.mark.parametrize("creator_name", [pytest.param("builtin", id="builtin"), pytest.param("venv", id="venv")])
@pytest.mark.parametrize("existing", [pytest.param(False, id="dangling"), pytest.param(True, id="existing")])
@pytest.mark.parametrize(
    "generated",
    [
        pytest.param(name, id=name)
        for name in ("pyvenv.cfg", "activate", "pip", "CACHEDIR.TAG", ".gitignore", "_virtualenv.py", "_virtualenv.pth")
    ],
)
def test_creator_replaces_generated_file_links(
    tmp_path: Path,
    creator_name: str,
    existing: bool,
    generated: str,
) -> None:
    command: Final = [
        str(tmp_path / "env"),
        "--creator",
        creator_name,
        "--pip",
        "embed",
        "--no-periodic-update",
    ]
    if generated.startswith("_virtualenv"):
        if (python39 := shutil.which("python3.9")) is None:
            pytest.skip("Python 3.9 is unavailable")
        command.extend(["--python", python39])
    session: Final = session_via_cli(command)
    session.creator.bin_dir.mkdir(parents=True)
    target: Final = session.creator.dest / "original"
    if existing:
        target.write_bytes(b"original")
    path = (
        session.creator.bin_dir / ("pip.exe" if generated == "pip" and os.name == "nt" else generated)
        if generated in {"activate", "pip"}
        else session.creator.dest / generated
    )
    if generated.startswith("_virtualenv"):
        path = session.creator.purelib / generated
    path.parent.mkdir(parents=True, exist_ok=True)
    path.symlink_to(target)
    with session:
        session.run()
    if existing and (generated == "CACHEDIR.TAG" or (generated == ".gitignore" and creator_name == "builtin")):
        assert path.is_symlink()
    else:
        assert not path.is_symlink()
    assert (target.read_bytes() if existing else target.exists()) == (b"original" if existing else False)


@pytest.mark.parametrize(
    "kind",
    [
        pytest.param("file", id="file"),
        pytest.param("symlink", id="symlink"),
        pytest.param("dangling", id="dangling"),
        pytest.param("junction", id="junction"),
    ],
)
def test_venv_prepares_real_executable_directory(tmp_path: Path, kind: str) -> None:
    session: Final = session_via_cli([str(tmp_path / "env"), "--creator", "venv", "--no-seed", "--activators="])
    session.creator.dest.mkdir()
    if kind == "file":
        session.creator.bin_dir.write_bytes(b"file")
    else:
        target: Final = session.creator.dest / "empty"
        if kind != "dangling":
            target.mkdir()
        if kind == "junction":
            if not IS_WIN:
                pytest.skip("requires Windows junctions")
            subprocess.run(
                ["cmd", "/c", "mklink", "/J", str(session.creator.bin_dir), str(target)],
                capture_output=True,
                check=True,
            )
        else:
            if not fs_supports_symlink():
                pytest.skip("requires directory symlinks")
            session.creator.bin_dir.symlink_to(target, target_is_directory=True)
    if kind == "file":
        with pytest.raises(NotADirectoryError, match="environment directory is not a real directory"):
            session.run()
    else:
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


@pytest.mark.parametrize("linked", [pytest.param(False, id="working-directory"), pytest.param(True, id="symlink")])
def test_resolved_destination_rejects_path_separator(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, linked: bool
) -> None:
    parent: Final = tmp_path / f"parent{os.pathsep}directory"
    parent.mkdir()
    if linked:
        if not fs_supports_symlink():
            pytest.skip("requires directory symlinks")
        (tmp_path / "link").symlink_to(parent, target_is_directory=True)
        monkeypatch.chdir(tmp_path)
    else:
        monkeypatch.chdir(parent)
    with pytest.raises(ArgumentTypeError, match="must not contain the path separator"):
        Creator.validate_dest("link/env" if linked else "env")


_LEGACY_DESTINATIONS: Final = [
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


def _non_success_exit_code(capsys, target):
    with pytest.raises(SystemExit) as context:
        run_with_catch(args=[target])
    assert context.value.code != 0
    out, err = capsys.readouterr()
    assert "SystemExit: " in out
    return err


def test_destination_exists_file(tmp_path, capsys) -> None:
    target = tmp_path / "out"
    target.write_text("", encoding="utf-8")
    err = _non_success_exit_code(capsys, str(target))
    msg = f"the destination {target!s} already exists and is a file"
    assert msg in err, err


@pytest.mark.skipif(sys.platform == "win32", reason="Windows only applies R/O to files")
def test_destination_not_write_able(tmp_path, capsys) -> None:
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        pytest.skip("no way to check permission restriction when running under root")

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
    from virtualenv.create.creator import HERE  # ruff:ignore[import-outside-top-level]

    paths = [p.resolve() for p in (Path(os.path.abspath(i)) for i in paths) if p.exists()]
    to_remove = [Path(HERE)]
    if os.environ.get("PYCHARM_HELPERS_DIR"):
        to_remove.extend((Path(os.environ["PYCHARM_HELPERS_DIR"]).parent, Path(os.path.expanduser("~")) / ".PyCharm"))
    return [i for i in paths if not any(str(i).startswith(str(t)) for t in to_remove)]


@pytest.fixture(scope="session")
def system(session_app_data):
    return get_env_debug_info(Path(CURRENT.system_executable), DEBUG_SCRIPT, session_app_data, os.environ)


CURRENT_CREATORS = [i for i in CreatorSelector.for_interpreter(CURRENT).key_to_class if i != "builtin"]


@pytest.mark.skipif("venv" not in CURRENT_CREATORS, reason="stdlib venv is unavailable")
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


@pytest.mark.skipif("venv" not in CURRENT_CREATORS, reason="stdlib venv is unavailable")
def test_venv_creator_accepts_plain_destination(tmp_path: Path) -> None:
    session: Final = cli_run([str(tmp_path / "environment"), "--creator", "venv", "--no-seed"])
    assert (session.creator.dest / "pyvenv.cfg").is_file()


@pytest.mark.parametrize(
    "junction",
    [
        pytest.param(
            False, id="symlink", marks=pytest.mark.skipif(not fs_supports_symlink(), reason="symlinks are unavailable")
        ),
        pytest.param(True, id="junction", marks=pytest.mark.skipif(os.name != "nt", reason="Windows junctions")),
    ],
)
@pytest.mark.parametrize(
    "creator_name",
    [
        pytest.param("builtin", id="builtin"),
        pytest.param(
            "venv",
            id="venv",
            marks=pytest.mark.skipif("venv" not in CURRENT_CREATORS, reason="stdlib venv is unavailable"),
        ),
    ],
)
@pytest.mark.parametrize("folder", [pytest.param("bin_dir", id="executables"), pytest.param("purelib", id="packages")])
def test_creator_replaces_directory_links(tmp_path: Path, creator_name: str, folder: str, junction: bool) -> None:
    session: Final = session_via_cli([str(tmp_path / "env"), "--creator", creator_name, "--no-seed"])
    session.creator.dest.mkdir()
    stored: Final = session.creator.dest / "stored"
    stored.mkdir()
    link: Final = session.creator.dest / getattr(session.creator, folder).relative_to(session.creator.dest).parts[0]
    if junction:
        subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(stored)], capture_output=True, check=True)
    else:
        link.symlink_to(stored, target_is_directory=True)
    with session:
        session.run()
    assert (link.resolve(), session.creator.exe.is_file(), list(stored.iterdir())) == (link, True, [])


CREATE_METHODS = []
for k, v in CreatorSelector.for_interpreter(CURRENT).key_to_meta.items():
    if k in CURRENT_CREATORS:
        if v.can_copy:
            if k == "venv" and CURRENT.implementation == "PyPy" and CURRENT.pypy_version_info >= [7, 3, 13]:
                continue  # https://foss.heptapod.net/pypy/pypy/-/issues/4019
            CREATE_METHODS.append((k, "copies"))
        if v.can_symlink:
            CREATE_METHODS.append((k, "symlinks"))


@pytest.mark.graalpy
@pytest.mark.parametrize(
    ("creator", "isolated"),
    [pytest.param(*i, id=f"{'-'.join(i[0])}-{i[1]}") for i in product(CREATE_METHODS, ["isolated", "global"])],
)
def test_create_no_seed(  # ruff:ignore[complex-structure, too-many-branches, too-many-arguments, too-many-statements]
    python,
    creator,
    isolated,
    system,
    coverage_env,
    special_name_dir,
) -> None:
    dest = special_name_dir
    creator_key, method = creator
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
    ]
    if isolated == "global":
        cmd.append("--system-site-packages")
    result = cli_run(cmd)
    creator = result.creator
    coverage_env()
    if IS_PYPY:
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

    # ensure the global site package is added or not, depending on flag
    global_sys_path = system_sys_path[-1]
    if isolated == "isolated":
        msg = "\n".join(str(j) for j in sys_path)
        msg = f"global sys path {global_sys_path!s} is in virtual environment sys path:\n{msg}"
        assert global_sys_path not in sys_path, msg
    else:
        common = []
        for left, right in zip(reversed(system_sys_path), reversed(sys_path)):
            if left == right:
                common.append(left)
            else:
                break

        def list_to_str(iterable):
            return [str(i) for i in iterable]

        assert common, "\n".join(difflib.unified_diff(list_to_str(sys_path), list_to_str(system_sys_path)))

    # test that the python executables in the bin directory are either:
    # - files
    # - absolute symlinks outside of the venv
    # - relative symlinks inside of the venv
    if sys.platform == "win32":
        exes = ("python.exe",)
    else:
        exes = ("python", f"python{sys.version_info.major}", f"python{sys.version_info.major}.{sys.version_info.minor}")
        if creator_key == "venv":
            # for venv some repackaging does not includes the pythonx.y
            exes = exes[:-1]
    for exe in exes:
        exe_path = creator.bin_dir / exe
        assert exe_path.exists(), "\n".join(str(i) for i in creator.bin_dir.iterdir())
        if not exe_path.is_symlink():  # option 1: a real file
            continue  # it was a file
        link = os.readlink(str(exe_path))
        if not os.path.isabs(link):  # option 2: a relative symlink
            continue
        # option 3: an absolute symlink, should point outside the venv
        assert not link.startswith(str(creator.dest))

    if IS_WIN and CURRENT.implementation == "CPython":
        python_w = creator.exe.parent / "pythonw.exe"
        assert python_w.exists()
        assert python_w.read_bytes() != creator.exe.read_bytes()

    git_ignore = (dest / ".gitignore").read_text(encoding="utf-8")
    assert git_ignore.splitlines() == ["# created by virtualenv automatically", "*"]


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


@pytest.mark.skipif(not CURRENT.has_venv, reason="requires venv")
@pytest.mark.parametrize("global_packages", [pytest.param(False, id="isolated"), pytest.param(True, id="global")])
def test_venv_configuration_uses_selected_options(tmp_path: Path, global_packages: bool) -> None:
    args: Final = [str(tmp_path / "env"), "--creator", "venv", "--no-seed"]
    if global_packages:
        args.append("--system-site-packages")
    session: Final = cli_run(args)
    session.creator.pyenv_cfg.path.write_text("vendor-marker = unused\n", encoding="utf-8")
    session.creator.set_pyenv_cfg()
    executable: Final = session.creator.interpreter.system_exe if CURRENT.implementation == "GraalPy" else None
    expected: Final = {
        "vendor-marker": None,
        "include-system-site-packages": str(global_packages).lower(),
        "venvlauncher_command": executable,
        "base-executable": executable,
    }
    assert {key: session.creator.pyenv_cfg.content.get(key) for key in expected} == expected


@pytest.mark.skipif(not CURRENT.has_venv or not fs_supports_symlink(), reason="requires venv and symlinks")
@pytest.mark.skipif(
    is_mac_os_framework(CURRENT) or is_macos_brew(CURRENT) or (IS_GRAALPY and not IS_WIN),
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


@pytest.mark.skipif(not CURRENT.has_venv, reason="requires interpreter with venv")
def test_venv_subprocess_skips_local_venv_module(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "venv").mkdir()
    (tmp_path / "venv" / "__init__.py").write_text("raise SystemExit('imported from the working directory')", "utf-8")
    monkeypatch.chdir(tmp_path)
    session: Final = cli_run([
        "-p",
        str(CURRENT.executable),
        str(tmp_path / "env"),
        "--without-pip",
        "--creator",
        "venv",
        "--no-periodic-update",
    ])
    assert (session.creator.dest / "pyvenv.cfg").is_file()


@pytest.mark.skipif(not CURRENT.has_venv, reason="requires interpreter with venv")
@pytest.mark.parametrize("mode", [pytest.param("--copies", id="copies"), pytest.param("--symlinks", id="symlinks")])
def test_venv_replaces_hard_linked_files(tmp_path: Path, mode: str) -> None:
    if mode == "--symlinks" and not fs_supports_symlink():
        pytest.skip("requires symlinks")
    if mode == "--copies" and (is_mac_os_framework(CURRENT) or is_macos_brew(CURRENT) or (IS_GRAALPY and not IS_WIN)):
        pytest.skip("stdlib creator requires symlinks on this runtime")
    session: Final = session_via_cli([str(tmp_path / "env"), "--creator", "venv", "--no-seed", "--activators=", mode])
    session.creator.bin_dir.mkdir(parents=True)
    names: Final = (
        ("python.exe", "pythonw.exe") if IS_WIN else ("python", "python3", f"python3.{CURRENT.version_info.minor}")
    )
    planted: Final = [session.creator.dest / "pyvenv.cfg", *(session.creator.bin_dir / name for name in names)]
    for path in planted:
        (tmp_path / f"{path.name}.original").write_bytes(b"original")
        os.link(tmp_path / f"{path.name}.original", path)
    session.run()
    assert [((tmp_path / f"{path.name}.original").read_bytes(), path.lstat().st_nlink) for path in planted] == [
        (b"original", 1)
    ] * len(planted)


@pytest.mark.skipif(not CURRENT.has_venv, reason="requires interpreter with venv")
def test_venv_fails_not_inline(tmp_path, capsys, mocker) -> None:
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        pytest.skip("no way to check permission restriction when running under root")

    def _session_via_cli(args, options=None, setup_logging=True, env=None):
        session = session_via_cli(args, options, setup_logging, env)
        assert session.creator.can_be_inline is False
        return session

    mocker.patch("virtualenv.run.session_via_cli", side_effect=_session_via_cli)
    before = tmp_path.stat().st_mode
    cfg_path = tmp_path / "pyvenv.cfg"
    cfg_path.write_text("", encoding="utf-8")
    cfg = str(cfg_path)
    try:
        os.chmod(cfg, stat.S_IREAD | stat.S_IRGRP | stat.S_IROTH)
        cmd = ["-p", str(CURRENT.executable), str(tmp_path), "--without-pip", "--creator", "venv"]
        with pytest.raises(SystemExit) as context:
            run(cmd)
        assert context.value.code != 0
    finally:
        os.chmod(cfg, before)
    out, err = capsys.readouterr()
    assert "subprocess call failed for" in out, out
    assert "Error:" in err, err


@pytest.mark.parametrize("creator", CURRENT_CREATORS)
@pytest.mark.parametrize("clear", [True, False], ids=["clear", "no_clear"])
def test_create_clear_resets(tmp_path, creator, clear, caplog) -> None:
    caplog.set_level(logging.DEBUG)
    if creator == "venv" and clear is False:
        pytest.skip("venv without clear might fail")
    marker = tmp_path / "magic"
    cmd = [str(tmp_path), "--seeder", "app-data", "--without-pip", "--creator", creator, "-vvv"]
    cli_run(cmd)

    marker.write_text("", encoding="utf-8")  # if we a marker file this should be gone on a clear run, remain otherwise
    assert marker.exists()

    cli_run(cmd + (["--clear"] if clear else []))
    assert marker.exists() is not clear


@pytest.mark.parametrize("creator", CURRENT_CREATORS)
@pytest.mark.parametrize("prompt", ["magic", "."])
def test_prompt_set(tmp_path: Path, creator: str, prompt: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    cmd = [str(tmp_path / "env"), "--seeder", "app-data", "--without-pip", "--creator", creator, "--prompt", prompt]
    result = cli_run(cmd)
    cfg = PyEnvCfg.from_file(result.creator.pyenv_cfg.path)
    if creator != "venv":
        expected = tmp_path.name if prompt == "." else prompt
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


@pytest.mark.parametrize("default_env", CURRENT_CREATORS, indirect=True)
def test_prompt_not_set_by_default(default_env: Session) -> None:
    assert "prompt" not in PyEnvCfg.from_file(default_env.creator.pyenv_cfg.path)


@pytest.mark.parametrize("default_env", CURRENT_CREATORS, indirect=True)
def test_version_keys_in_pyenv_cfg(default_env: Session) -> None:
    cfg = PyEnvCfg.from_file(default_env.creator.pyenv_cfg.path)
    version_info = default_env.creator.interpreter.version_info
    assert cfg["python-version"] == f"{version_info.major}.{version_info.minor}"
    assert "version" in cfg
    parts = cfg["version"].split(".")
    assert len(parts) == 3
    assert all(p.isdigit() for p in parts)


@pytest.mark.parametrize("default_env", [c for c in CURRENT_CREATORS if c != "venv"], indirect=True)
def test_executable_and_command_keys(default_env: Session) -> None:
    cfg = PyEnvCfg.from_file(default_env.creator.pyenv_cfg.path)
    assert "executable" in cfg
    assert Path(cfg["executable"]).exists()
    assert "command" in cfg
    assert "virtualenv" in cfg["command"]


@pytest.mark.parametrize("default_env", [c for c in CURRENT_CREATORS if c != "venv"], indirect=True)
def test_include_dir_created(default_env: Session) -> None:
    if sys.platform == "win32":
        include = default_env.creator.dest / "Include"
    else:
        include = default_env.creator.dest / "include"
    assert include.is_dir()


@pytest.mark.parametrize("default_env", CURRENT_CREATORS, indirect=True)
def test_home_path_is_exe_parent(default_env: Session) -> None:
    cfg = PyEnvCfg.from_file(default_env.creator.pyenv_cfg.path)

    # Cannot assume "home" path is a specific value as path resolution may change
    # between versions (symlinks, framework paths, etc) but we can check that a
    # python executable is present from the configured path per PEP 405
    if sys.platform == "win32":
        exes = ("python.exe",)
    else:
        exes = (
            "python",
            f"python{sys.version_info.major}",
            f"python{sys.version_info.major}.{sys.version_info.minor}",
        )

    assert any(os.path.exists(os.path.join(cfg["home"], exe)) for exe in exes)


@pytest.mark.skipif(IS_WIN or not fs_supports_symlink(), reason="requires POSIX interpreter aliases")
@pytest.mark.parametrize(
    "mode",
    [
        pytest.param(
            "--copies",
            id="copy",
            marks=pytest.mark.skipif(
                is_macos_brew(CURRENT) or is_mac_os_framework(CURRENT),
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


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX only")
@pytest.mark.skipif(
    bool(CURRENT.sysconfig_vars.get("PYTHONFRAMEWORK")),
    reason="framework builds self-locate via dyld and keep the recorded path",
)
@pytest.mark.usefixtures("temp_app_data")
def test_home_resolves_executable_only_symlink(tmp_path: Path) -> None:
    """An executable-only symlink must not be recorded as home / base-executable (issue #3157)."""
    system_exe = CURRENT.system_executable
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


@pytest.mark.usefixtures("current_fastest")
def test_create_long_path(tmp_path) -> None:
    if sys.platform == "darwin":
        max_shebang_length = 512
    else:
        max_shebang_length = 127
    # filenames can be at most 255 long on macOS, so split to to levels
    count = max_shebang_length - len(str(tmp_path))
    folder = tmp_path / ("a" * (count // 2)) / ("b" * (count // 2)) / "c"
    folder.mkdir(parents=True)

    cmd = [str(folder), "--without-pip"]
    result = cli_run(cmd)
    subprocess.check_call([str(result.creator.exe), "--version"])


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


def test_install_patch_skipped_on_py310(tmp_path, mocker) -> None:
    creator = mocker.MagicMock(purelib=tmp_path, interpreter=mocker.MagicMock(version_info=(3, 10, 0)))
    creator.env_patch_text.return_value = "import _virtualenv"
    api.ViaGlobalRefApi.install_patch(creator)
    assert not (tmp_path / "_virtualenv.pth").exists()
    assert not (tmp_path / "_virtualenv.py").exists()
    creator.env_patch_text.assert_not_called()


def test_install_patch_written_on_py39(tmp_path, mocker) -> None:
    creator = mocker.MagicMock(purelib=tmp_path, interpreter=mocker.MagicMock(version_info=(3, 9, 21)))
    creator.env_patch_text.return_value = "import _virtualenv"
    api.ViaGlobalRefApi.install_patch(creator)
    assert (tmp_path / "_virtualenv.pth").read_text(encoding="utf-8") == "import _virtualenv"
    assert (tmp_path / "_virtualenv.py").read_text(encoding="utf-8") == "import _virtualenv"


def list_files(path):
    result = ""
    for root, _, files in os.walk(path):
        level = root.replace(path, "").count(os.sep)
        indent = " " * 4 * level
        result += f"{indent}{os.path.basename(root)}/\n"
        sub = " " * 4 * (level + 1)
        for f in files:
            result += f"{sub}{f}\n"
    return result


@pytest.mark.skipif(is_macos_brew(CURRENT), reason="no copy on brew")
@pytest.mark.skip(reason="https://github.com/pypa/setuptools/issues/4640")
def test_zip_importer_can_import_setuptools(tmp_path) -> None:
    """We're patching the loaders so might fail on r/o loaders, such as zipimporter on CPython<3.8"""
    result = cli_run(
        [str(tmp_path / "venv"), "--activators", "", "--no-pip", "--no-wheel", "--copies", "--setuptools", "bundle"],
    )
    zip_path = tmp_path / "site-packages.zip"
    with zipfile.ZipFile(str(zip_path), "w", zipfile.ZIP_DEFLATED) as zip_handler:
        lib = str(result.creator.purelib)
        for root, _, files in os.walk(lib):
            base = root[len(lib) :].lstrip(os.pathsep)
            for file in files:
                if not file.startswith("_virtualenv"):
                    zip_handler.write(filename=os.path.join(root, file), arcname=os.path.join(base, file))
    for folder in result.creator.purelib.iterdir():
        if not folder.name.startswith("_virtualenv"):
            if folder.is_dir():
                shutil.rmtree(str(folder), ignore_errors=True)
            else:
                folder.unlink()
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
    path = [str(site_packages)]
    if "PYTHONPATH" in env:
        path.append(env["PYTHONPATH"])
    env["PYTHONPATH"] = os.pathsep.join(path)
    out = subprocess.check_output(
        [str(session.creator.exe), "-c", r"import sys; print(sys.testpth)"],
        text=True,
        env=env,
        encoding="utf-8",
    )
    assert out == "ok\n"


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

    env_site_packages = [str(session.creator.purelib), str(session.creator.platlib)]
    if not fs_is_case_sensitive():
        env_site_packages = [x.lower() for x in env_site_packages]
        site_packages = [x.lower() for x in site_packages]
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
    cmd = [str(tmp_path), "--without-pip"]
    result = cli_run(cmd)
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


@pytest.mark.graalpy
@pytest.mark.parametrize("python_path_on", [True, False], ids=["on", "off"])
def test_python_path(monkeypatch, tmp_path, python_path_on) -> None:
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
    python_path_env = os.pathsep.join(python_paths)
    monkeypatch.setenv("PYTHONPATH", python_path_env)

    extra_all = _get_sys_path(None if python_path_on else "-E")
    if python_path_on:
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
    else:
        assert base == extra_all


# Make sure that the venv creator works on systems where vendor-delivered files
# (specifically venv scripts delivered with Python itself) are not writable.
#
# https://github.com/pypa/virtualenv/issues/2419
@pytest.mark.skipif("venv" not in CURRENT_CREATORS, reason="test needs venv creator")
def test_venv_creator_without_write_perms(tmp_path, mocker) -> None:
    from virtualenv.run.session import Session  # ruff:ignore[import-outside-top-level]

    prev = Session._create  # ruff:ignore[private-member-access]

    def func(self) -> None:
        prev(self)
        scripts_dir = self.creator.dest / "bin"
        for script in scripts_dir.glob("*ctivate*"):
            script.chmod(stat.S_IREAD | stat.S_IRGRP | stat.S_IROTH)

    mocker.patch("virtualenv.run.session.Session._create", side_effect=func, autospec=True)

    cmd = [str(tmp_path), "--seeder", "app-data", "--without-pip", "--creator", "venv"]
    cli_run(cmd)


def test_fallback_to_copies_if_symlink_unsupported(tmp_path, python, mocker) -> None:
    """Test that creating a virtual environment falls back to copies when filesystem has no symlink support."""
    if is_macos_brew(PythonInfo.from_exe(python)):
        pytest.skip("brew python on darwin may not support copies, which is tested separately")

    # Given a filesystem that does not support symlinks
    mocker.patch("virtualenv.create.via_global_ref.api.fs_supports_symlink", return_value=False)

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


def test_fail_gracefully_if_no_method_supported(tmp_path, python, mocker) -> None:
    """Test that virtualenv fails gracefully when no creation method is supported."""
    # Given a filesystem that does not support symlinks
    mocker.patch("virtualenv.create.via_global_ref.api.fs_supports_symlink", return_value=False)

    # And a creator that does not support copying
    if not is_macos_brew(PythonInfo.from_exe(python)):
        original_init = api.ViaGlobalRefMeta.__init__

        def new_init(self, *args, **kwargs) -> None:
            original_init(self, *args, **kwargs)
            self.copy_error = "copying is not supported"

        mocker.patch("virtualenv.create.via_global_ref.api.ViaGlobalRefMeta.__init__", new=new_init)

    # When creating a virtual environment
    with pytest.raises(RuntimeError) as excinfo:
        cli_run(
            [
                "-p",
                str(python),
                str(tmp_path),
                "--without-pip",
            ],
        )

    # Then a RuntimeError should be raised with a detailed message
    assert "neither symlink or copy method supported" in str(excinfo.value)
    assert "symlink: the filesystem does not supports symlink" in str(excinfo.value)
    interpreter = PythonInfo.from_exe(python)
    if is_macos_brew(interpreter):
        assert "copy: Brew disables copy creation" in str(excinfo.value)
    elif is_mac_os_framework(interpreter):
        assert "copy: macOS framework builds do not support copy-based virtual environments" in str(excinfo.value)
    else:
        assert "copy: copying is not supported" in str(excinfo.value)


def test_pyenv_cfg_preserves_symlinks(tmp_path) -> None:
    """Test that PyEnvCfg.write() preserves symlinks and doesn't resolve them (issue #2770)."""
    # Create a real directory and a symlink to it
    real_dir = tmp_path / "real_directory"
    real_dir.mkdir()
    real_file = real_dir / "some_file.txt"
    real_file.write_text("test", encoding="utf-8")

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
    ("key", "value", "is_path"),
    [
        pytest.param("home", "base", True, id="home"),
        pytest.param("python-version", "3.14", False, id="python-version"),
        pytest.param("version", "3.14.6", False, id="version"),
        pytest.param("implementation", "CPython", False, id="implementation"),
        pytest.param("include-system-site-packages", "true", False, id="include-system-site-packages"),
    ],
)
def test_pyenv_cfg_value_naming_entry_in_cwd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, key: str, value: str, is_path: bool
) -> None:
    (tmp_path / value).mkdir()
    monkeypatch.chdir(tmp_path)
    cfg = PyEnvCfg(OrderedDict({key: value}), tmp_path / "pyvenv.cfg")

    cfg.write()

    assert PyEnvCfg.from_file(cfg.path).content == {key: os.path.abspath(value) if is_path else value}


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


@pytest.mark.skipif(IS_WIN, reason="POSIX locales")
@pytest.mark.usefixtures("_no_coverage")
def test_default_activators_allow_legacy_locale(tmp_path: Path) -> None:
    locales: Final = subprocess.check_output(["locale", "-a"], text=True, encoding="utf-8").splitlines()
    if (locale := next((name for name in locales if name.lower() == "aa_dj.iso88591"), None)) is None:
        pytest.skip("Latin-1 locale is unavailable")
    parent: Final = os.fsencode(tmp_path) + b"/calf\xe9"
    os.mkdir(parent)
    result: Final = subprocess.run(
        [sys.executable, "-m", "virtualenv", "env", "--no-seed"],
        cwd=parent,
        env={**os.environ, "LC_ALL": locale, "PYTHONUTF8": "0", "PYTHONCOERCECLOCALE": "0"},
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


@pytest.mark.skipif(not CURRENT.has_venv, reason="requires interpreter with venv")
@pytest.mark.skipif(CURRENT.implementation != "CPython", reason="only CPython rejects an invalid PYTHONHOME")
def test_venv_subprocess_respects_pythonhome(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    session = session_via_cli(["-p", str(CURRENT.executable), str(tmp_path / "env"), "--no-seed", "--creator", "venv"])
    monkeypatch.setenv("PYTHONHOME", str(tmp_path / "missing-home"))
    with pytest.raises(ProcessCallFailedError):
        session.run()
