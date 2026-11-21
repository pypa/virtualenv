from __future__ import annotations

import contextlib
import csv
import errno
import hashlib
import io
import logging
import os
import shlex
import signal
import sys
import zipfile
from base64 import urlsafe_b64encode
from concurrent.futures import Future, ThreadPoolExecutor
from importlib.metadata import PathDistribution
from pathlib import Path
from shutil import copy2
from stat import S_IREAD, S_IWGRP, S_IWOTH, S_IWUSR
from subprocess import PIPE, STDOUT, Popen, check_call, run
from threading import Barrier, BrokenBarrierError, Event, Thread, current_thread, main_thread
from typing import TYPE_CHECKING, Final

import pytest
from python_discovery import PythonInfo
from python_discovery import _cached_py_info as cached_py_info  # ruff:ignore[import-private-name]  # simplint: ignore[private-import-path]  # disk cache  # fmt: skip

from virtualenv.app_data import ReadOnlyAppData
from virtualenv.info import IS_GRAALPY, IS_PYPY, fs_supports_symlink
from virtualenv.run import cli_run
from virtualenv.seed.embed.via_app_data.pip_install.base import PipInstall, shell_shebang
from virtualenv.seed.embed.via_app_data.pip_install.copy import CopyPipInstall
from virtualenv.seed.embed.via_app_data.pip_install.symlink import SymlinkPipInstall
from virtualenv.seed.wheels.embed import BUNDLE_FOLDER, BUNDLE_SHA256, BUNDLE_SUPPORT, get_embed_wheel
from virtualenv.util.path import safe_delete
from virtualenv.version import __version__

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator
    from importlib.metadata import PackagePath
    from subprocess import CompletedProcess

    from pytest_mock import MockerFixture, MockType, SpyType

    from virtualenv.run.session import Session

_SCRIPTS_DIR: Final[str] = "Scripts" if os.name == "nt" else "bin"
_PIP_EXE: Final[str] = "pip.exe" if os.name == "nt" else "pip"


@pytest.mark.parametrize(
    ("config_text", "extra_env", "extra_args"),
    [
        pytest.param("", {"VIRTUALENV_SYMLINK_APP_DATA": "true"}, [], id="environment"),
        pytest.param("[virtualenv]\nsymlink_app_data = true\n", {}, [], id="configuration"),
        pytest.param("", {}, ["--symlink-app-data"], id="command-line"),
    ],
)
def test_transient_seed_survives_cache_cleanup(
    tmp_path: Path, config_text: str, extra_env: dict[str, str], extra_args: list[str], unusable_cache: Path
) -> None:
    config: Final[Path] = tmp_path / "virtualenv.ini"
    config.write_text(config_text, encoding="utf-8")
    env: Final[dict[str, str]] = {
        **os.environ,
        "VIRTUALENV_CONFIG_FILE": str(config),
        "VIRTUALENV_OVERRIDE_APP_DATA": str(unusable_cache),
        **extra_env,
    }
    args: Final[list[str]] = [str(tmp_path / "env"), "--no-periodic-update", "--no-setuptools", *extra_args]
    session: Final[Session] = cli_run(args, env=env)
    assert (
        session.creator.app_data.transient,
        Path(str(session.creator.app_data)).exists(),
        (session.creator.purelib / "pip" / "__init__.py").is_file(),
    ) == (True, False, True)


def test_transient_seed_reports_copy_fallback(
    tmp_path: Path, caplog: pytest.LogCaptureFixture, unusable_cache: Path
) -> None:
    caplog.set_level(logging.DEBUG)
    cli_run(
        [str(tmp_path / "env"), "--no-periodic-update", "--no-setuptools"],
        env={**os.environ, "VIRTUALENV_OVERRIDE_APP_DATA": str(unusable_cache), "VIRTUALENV_SYMLINK_APP_DATA": "true"},
        setup_logging=False,
    )
    assert "copy seed packages because temporary app-data is removed after creation" in caplog.text


@pytest.fixture
def unusable_cache(tmp_path: Path) -> Path:
    blocked: Final[Path] = tmp_path / "blocked"
    blocked.touch()
    return blocked / "cache"


@pytest.mark.skipif(sys.platform == "win32", reason="SIGINT delivery differs on Windows")
def test_interrupt_waits_for_seed_before_temp_cleanup(tmp_path: Path, unusable_cache: Path) -> None:
    (tmp_path / "temp").mkdir()
    process = Popen(
        [sys.executable, "-m", "virtualenv", "--no-periodic-update", "-vvv", str(tmp_path / "env")],
        cwd=tmp_path,
        env={
            **os.environ,
            "TMPDIR": str(tmp_path / "temp"),
            "VIRTUALENV_OVERRIDE_APP_DATA": str(unusable_cache),
        },
        stdout=PIPE,
        stderr=STDOUT,
        text=True,
        encoding="utf-8",
    )
    assert process.stdout is not None
    lines: list[str] = []
    interrupted = Event()

    def interrupt_seed() -> None:
        for line in process.stdout:
            lines.append(line)
            if "build install image for pip" in line and not interrupted.is_set():
                process.send_signal(signal.SIGINT)
                interrupted.set()

    watcher = Thread(target=interrupt_seed)
    watcher.start()
    try:
        process.wait(timeout=120)
    finally:
        process.kill()
        process.wait(timeout=5)
        watcher.join(timeout=5)

    assert interrupted.is_set()
    cache_line = next(line for line in lines if "created temporary app data folder" in line)
    cache = Path(cache_line.split(" folder ", 1)[1].split(" [DEBUG", 1)[0])
    cleanup_index = next(index for index, line in enumerate(lines) if "remove temporary app data folder" in line)
    release_index = next(
        index for index, line in enumerate(lines) if " released on " in line and "CopyPipInstall" in line
    )
    assert (release_index < cleanup_index, cache.exists(), bool(list((tmp_path / "env").rglob("pip/__init__.py")))) == (
        True,
        False,
        True,
    )


def test_second_interrupt_exits_and_next_run_finishes_seed(tmp_path: Path) -> None:
    env: Final[Path] = tmp_path / "env"
    cache: Final[Path] = tmp_path / "cache"
    args: Final[list[str]] = ["--app-data", str(cache), "--no-periodic-update", "--no-setuptools", str(env)]
    script: Final[str] = """
import os
import sys
from _thread import interrupt_main
from threading import Event, Thread
from virtualenv.__main__ import run_with_catch
from virtualenv.seed.embed.via_app_data.pip_install.base import PipInstall

def block(self, archive, folder):
    print("staging", folder, flush=True)
    Event().wait()

def watch_stdin():
    for _ in sys.stdin:
        interrupt_main()

if os.name == "nt":
    Thread(target=watch_stdin, daemon=True).start()
PipInstall._populate_image = block
run_with_catch()
"""
    with Popen([sys.executable, "-c", script, *args], stdin=PIPE, stdout=PIPE, stderr=STDOUT, text=True) as process:
        assert process.stdout is not None
        staging: list[Path] = []
        signals: list[str] = []

        def interrupt_seed() -> None:
            for line in process.stdout:
                if line.startswith("staging "):
                    staging.append(Path(line.removeprefix("staging ").rstrip()))
                    signals.append("build")
                elif "Press Ctrl+C again" in line:
                    signals.append("wait")
                else:
                    continue
                if os.name == "nt":
                    # A Windows console interrupt cannot target just this child in the test runner's console.
                    assert process.stdin is not None
                    process.stdin.write("\n")
                    process.stdin.flush()
                else:
                    process.send_signal(signal.SIGINT)

        watcher = Thread(target=interrupt_seed)
        watcher.start()
        try:
            process.wait(timeout=30)
        finally:
            process.kill()
            process.wait(timeout=5)
            watcher.join(timeout=5)

    assert (signals, process.returncode, [path.is_dir() for path in staging]) == (["build", "wait"], 130, [True])
    session = cli_run(args)
    assert (staging[0].exists(), (session.creator.purelib / "pip" / "__init__.py").is_file()) == (False, True)


def test_repeated_interrupts_wait_for_seed_worker(tmp_path: Path, unusable_cache: Path, mocker: MockerFixture) -> None:
    started, release, finished = Event(), Event(), Event()
    original_build = PipInstall.build_image

    def build_image(installer: PipInstall) -> None:
        started.set()
        assert release.wait(timeout=5)
        original_build(installer)
        finished.set()

    mocker.patch.object(PipInstall, "build_image", autospec=True, side_effect=build_image)
    original_submit, original_wait = ThreadPoolExecutor.submit, Event.wait
    submit_calls = 0
    interrupts = 0

    def submit(executor: ThreadPoolExecutor, fn: Callable[..., None], *args: object, **kwargs: object) -> Future[None]:
        nonlocal submit_calls
        future = original_submit(executor, fn, *args, **kwargs)
        submit_calls += 1
        return future

    def interrupt_wait(event: Event, timeout: float | None = None) -> bool:
        nonlocal interrupts
        if submit_calls >= 2 and current_thread() is main_thread() and event is not started:
            assert original_wait(started, timeout=30)
            if interrupts < 2:
                interrupts += 1
                raise KeyboardInterrupt
            release.set()
        return original_wait(event, timeout)

    mocker.patch.object(ThreadPoolExecutor, "submit", autospec=True, side_effect=submit)
    mocker.patch.object(Event, "wait", autospec=True, side_effect=interrupt_wait)
    with pytest.raises(KeyboardInterrupt):
        cli_run(
            [str(tmp_path / "env"), "--no-periodic-update", "--no-setuptools"],
            env={**os.environ, "VIRTUALENV_OVERRIDE_APP_DATA": str(unusable_cache)},
        )
    assert (interrupts, finished.is_set()) == (2, True)


def test_interrupt_during_worker_submission_waits_for_seed(
    tmp_path: Path, unusable_cache: Path, mocker: MockerFixture
) -> None:
    started, release, finished = Event(), Event(), Event()
    original_build = PipInstall.build_image

    def build_image(installer: PipInstall) -> None:
        started.set()
        assert release.wait(timeout=5)
        original_build(installer)
        finished.set()

    mocker.patch.object(PipInstall, "build_image", autospec=True, side_effect=build_image)
    original_submit = ThreadPoolExecutor.submit
    submit_calls = 0
    interrupted = False
    wait_interrupted = False

    def submit(executor: ThreadPoolExecutor, fn: Callable[..., None], *args: object, **kwargs: object) -> Future[None]:
        nonlocal submit_calls, interrupted
        future = original_submit(executor, fn, *args, **kwargs)
        submit_calls += 1
        if submit_calls == 2 and not interrupted:
            assert started.wait(timeout=5)
            interrupted = True
            raise KeyboardInterrupt
        return future

    original_wait = Event.wait

    def interrupt_wait(event: Event, timeout: float | None = None) -> bool:
        nonlocal wait_interrupted
        if interrupted and current_thread() is main_thread() and not wait_interrupted:
            wait_interrupted = True
            release.set()
            raise KeyboardInterrupt
        return original_wait(event, timeout)

    mocker.patch.object(ThreadPoolExecutor, "submit", autospec=True, side_effect=submit)
    mocker.patch.object(Event, "wait", autospec=True, side_effect=interrupt_wait)
    with pytest.raises(KeyboardInterrupt):
        cli_run(
            [str(tmp_path / "env"), "--no-periodic-update", "--no-setuptools"],
            env={**os.environ, "VIRTUALENV_OVERRIDE_APP_DATA": str(unusable_cache)},
        )
    assert (wait_interrupted, finished.is_set()) == (True, True)


def test_interrupt_before_queueing_cancels_pending_install(tmp_path: Path, mocker: MockerFixture) -> None:
    original_submit = ThreadPoolExecutor.submit
    queued: list[Callable[[], None]] = []
    calls = 0

    def submit(executor: ThreadPoolExecutor, fn: Callable[..., None], *args: object, **kwargs: object) -> Future[None]:
        nonlocal calls
        calls += 1
        if calls == 2:
            queued.append(fn)
            raise KeyboardInterrupt
        return original_submit(executor, fn, *args, **kwargs)

    original_set = Event.set
    interrupted_cancel = False

    def interrupt_cancel(event: Event) -> None:
        nonlocal interrupted_cancel
        if queued and current_thread() is main_thread() and not interrupted_cancel:
            interrupted_cancel = True
            raise KeyboardInterrupt
        original_set(event)

    mocker.patch.object(ThreadPoolExecutor, "submit", autospec=True, side_effect=submit)
    mocker.patch.object(Event, "set", autospec=True, side_effect=interrupt_cancel)
    with pytest.raises(KeyboardInterrupt):
        cli_run([str(tmp_path / "env"), "--no-periodic-update", "--no-setuptools"])
    queued[0]()
    assert (interrupted_cancel, list((tmp_path / "env").rglob("pip/__init__.py"))) == (True, [])


def test_seed_worker_runs_when_executor_rejects_submission(
    tmp_path: Path, unusable_cache: Path, mocker: MockerFixture
) -> None:
    original_submit = ThreadPoolExecutor.submit
    rejected = False

    submit_calls = 0

    def submit(executor: ThreadPoolExecutor, fn: Callable[..., None], *args: object, **kwargs: object) -> Future[None]:
        nonlocal submit_calls, rejected
        submit_calls += 1
        if submit_calls == 2 and not rejected:
            rejected = True
            msg = "cannot start worker"
            raise RuntimeError(msg)
        return original_submit(executor, fn, *args, **kwargs)

    mocker.patch.object(ThreadPoolExecutor, "submit", autospec=True, side_effect=submit)
    session = cli_run(
        [str(tmp_path / "env"), "--no-periodic-update", "--no-setuptools"],
        env={**os.environ, "VIRTUALENV_OVERRIDE_APP_DATA": str(unusable_cache)},
    )
    assert (
        rejected,
        (session.creator.purelib / "pip" / "__init__.py").is_file(),
        Path(str(session.creator.app_data)).exists(),
    ) == (True, True, False)


@pytest.mark.parametrize(
    ("config_text", "env_vars", "flags"),
    [
        pytest.param("", {"VIRTUALENV_SYMLINK_APP_DATA": "true"}, (), id="environment"),
        pytest.param("[virtualenv]\nsymlink_app_data = true\n", {}, (), id="configuration"),
        pytest.param("", {}, ("--symlink-app-data",), id="command-line"),
    ],
)
@pytest.mark.usefixtures("symlinks_unsupported")
def test_seed_copies_when_symlinks_unsupported(
    tmp_path: Path, config_text: str, env_vars: dict[str, str], flags: tuple[str, ...]
) -> None:
    config: Final[Path] = tmp_path / "virtualenv.ini"
    config.write_text(config_text, encoding="utf-8")
    session: Final[Session] = cli_run(
        [
            str(tmp_path / "env"),
            "--app-data",
            str(tmp_path / "cache"),
            "--no-periodic-update",
            "--no-setuptools",
            *flags,
        ],
        env={**os.environ, "VIRTUALENV_CONFIG_FILE": str(config), **env_vars},
    )
    pip: Final[Path] = session.creator.purelib / "pip"
    assert (
        session.creator.app_data.transient,
        pip.is_symlink(),
        (pip / "__init__.py").is_file(),
    ) == (False, False, True)


@pytest.mark.usefixtures("symlinks_unsupported")
def test_seed_reports_copy_fallback_when_symlinks_unsupported(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG)
    cli_run(
        [str(tmp_path / "env"), "--app-data", str(tmp_path / "cache"), "--no-periodic-update", "--no-setuptools"],
        env={**os.environ, "VIRTUALENV_SYMLINK_APP_DATA": "true"},
        setup_logging=False,
    )
    assert "copy seed packages because the filesystem does not support symlinks" in caplog.text


@pytest.fixture
def symlinks_unsupported(mocker: MockerFixture) -> None:
    mocker.patch(
        "virtualenv.seed.embed.via_app_data.via_app_data.fs_supports_symlink", autospec=True, return_value=False
    )


@pytest.mark.skipif(not fs_supports_symlink(), reason="requires symlinks")
@pytest.mark.parametrize(
    ("where", "name"),
    [pytest.param("cwd", "compileall.py", id="cwd-module"), pytest.param("purelib", "planted.pth", id="site-pth")],
)
def test_seed_image_compiles_in_isolation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, where: str, name: str
) -> None:
    cmd: Final[list[str]] = [
        str(tmp_path / "env"),
        "--app-data",
        str(tmp_path / "cache"),
        "--symlink-app-data",
        "--no-periodic-update",
        "--no-setuptools",
    ]
    purelib: Final[Path] = cli_run([*cmd, "--without-pip"]).creator.purelib
    marker: Final[Path] = tmp_path / "marker"
    planted: Final[Path] = {"cwd": tmp_path, "purelib": purelib}[where] / name
    planted.write_text(f"import pathlib; pathlib.Path({str(marker)!r}).touch()", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    session: Final[Session] = cli_run(cmd)
    assert list((session.creator.purelib / "pip" / "__pycache__").glob("__init__.*.pyc"))
    assert not marker.exists()


@pytest.mark.usefixtures("_no_coverage")
@pytest.mark.parametrize(
    ("metadata_file", "content"),
    [
        pytest.param("top_level.txt", "pip\n{dest}\n", id="top-level-env-root"),
        pytest.param("top_level.txt", "pip\n\n", id="top-level-blank"),
        pytest.param("RECORD", "{record}\n{outside},,", id="record-traversal"),
    ],
)
def test_seed_metadata_cleanup_stays_inside_package(
    tmp_path: Path, caplog: pytest.LogCaptureFixture, metadata_file: str, content: str
) -> None:
    args: Final[list[str]] = [str(tmp_path / "env"), "--pip", "embed", "--no-periodic-update"]
    session: Final[Session] = cli_run(args, setup_logging=False)
    purelib: Final[Path] = session.creator.purelib
    markers: Final[list[Path]] = [tmp_path / "keep.txt", session.creator.dest / "keep.txt", purelib / "keep.txt"]
    for marker in markers:
        marker.write_text("keep", encoding="utf-8")
    dist_info: Final[Path] = next(purelib.glob("pip-*.dist-info"))
    (dist_info / metadata_file).write_text(
        content.format(
            dest=session.creator.dest,
            outside=os.path.relpath(markers[0], purelib),
            record=(dist_info / "RECORD").read_text(encoding="utf-8"),
        ),
        encoding="utf-8",
    )
    cli_run(args, setup_logging=False)
    assert (
        [i.exists() for i in markers],
        (purelib / "pip" / "__init__.py").is_file(),
        "skip removal of" in caplog.text,
    ) == (
        [True, True, True],
        True,
        True,
    )


@pytest.mark.skipif(not fs_supports_symlink(), reason="symlinks are unavailable")
def test_seed_metadata_unlinks_symlink_without_following(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    args: Final[list[str]] = [str(tmp_path / "env"), "--pip", "embed", "--no-periodic-update"]
    session: Final[Session] = cli_run(args, setup_logging=False)
    outside: Final[Path] = tmp_path / "outside"
    outside.mkdir()
    (outside / "keep.txt").write_text("keep", encoding="utf-8")
    link: Final[Path] = session.creator.purelib / "linked"
    link.symlink_to(outside, target_is_directory=True)
    record: Final[Path] = next(session.creator.purelib.glob("pip-*.dist-info")) / "RECORD"
    record.write_text(f"{record.read_text(encoding='utf-8')}\nlinked,,", encoding="utf-8")
    cli_run(args, setup_logging=False)
    assert (link.is_symlink(), (outside / "keep.txt").exists(), "skip removal of" in caplog.text) == (
        False,
        True,
        False,
    )


@pytest.mark.skipif(os.name == "nt" or not fs_supports_symlink(), reason="requires POSIX parent links")
@pytest.mark.parametrize(
    ("create", "delete", "name"),
    [
        pytest.param(Path.touch, Path.unlink, "remove_file", id="file"),
        pytest.param(Path.mkdir, safe_delete, "safe_delete", id="directory"),
    ],
)
def test_seed_metadata_removes_checked_path(
    tmp_path: Path, mocker: MockerFixture, create: Callable[[Path], None], delete: Callable[[Path], None], name: str
) -> None:
    env: Final[Path] = tmp_path / "env"
    purelib: Final[Path] = env / "lib" / "site-packages"
    dist_info: Final[Path] = purelib / "seed-0.dist-info"
    dist_info.mkdir(parents=True)
    target: Final[Path] = env / "deep" / "a" / "b" / "c"
    target.mkdir(parents=True)
    outside_target: Final[Path] = tmp_path / "a" / "b" / "c"
    outside_target.mkdir(parents=True)
    inside: Final[Path] = env / "deep" / "keep"
    outside: Final[Path] = tmp_path / "keep"
    create(inside)
    create(outside)
    (dist_info / "RECORD").write_text("linked/../../../keep,,\n", encoding="utf-8")
    link: Final[Path] = purelib / "linked"
    link.symlink_to(target, target_is_directory=True)

    def replace_link_then_delete(path: Path) -> None:
        if link.is_symlink():
            link.unlink()
            link.symlink_to(outside_target, target_is_directory=True)
        delete(path)

    mocker.patch(
        f"virtualenv.seed.embed.via_app_data.pip_install.base.{name}",
        side_effect=replace_link_then_delete,
        autospec=True,
    )
    CopyPipInstall._uninstall_dist(dist_info, env)  # ruff:ignore[private-member-access]  # metadata cleanup
    assert (inside.exists(), outside.exists()) == (False, True)


@pytest.mark.skipif(sys.platform != "linux" or not fs_supports_symlink(), reason="requires Linux path limits")
def test_seed_metadata_skips_unresolvable_parent_link(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    env: Final[Path] = tmp_path / "env"
    purelib: Final[Path] = env / "lib" / "site-packages"
    dist_info: Final[Path] = purelib / "seed-0.dist-info"
    dist_info.mkdir(parents=True)
    outside: Final[Path] = tmp_path / "outside"
    outside.mkdir()
    (outside / "notes").write_text("keep", encoding="utf-8")
    deep = purelib
    # The expanded out path must exceed Linux's 4095-byte limit.
    while (remaining := 4093 - len(str(deep))) > 1:
        deep /= "d" * min(200, remaining - 1)
        deep.mkdir()
    (purelib / "hop").symlink_to(deep.relative_to(purelib), target_is_directory=True)
    (purelib / "hop" / "out").symlink_to(os.path.relpath(outside, deep), target_is_directory=True)
    (dist_info / "RECORD").write_text("hop/out/notes,,\n", encoding="utf-8")
    assert env.resolve() in (purelib / "hop" / "out" / "notes").resolve().parents
    CopyPipInstall._uninstall_dist(dist_info, env)  # ruff:ignore[private-member-access]  # metadata cleanup
    assert ((outside / "notes").read_text(encoding="utf-8"), "cannot resolve it" in caplog.text) == ("keep", True)


@pytest.mark.skipif(os.name != "nt", reason="Windows junctions")
def test_seed_metadata_removes_junction_without_following(tmp_path: Path) -> None:
    env: Final[Path] = tmp_path / "env"
    purelib: Final[Path] = env / "Lib" / "site-packages"
    dist_info: Final[Path] = purelib / "seed-0.dist-info"
    dist_info.mkdir(parents=True)
    target: Final[Path] = env / "target"
    target.mkdir()
    (target / "keep.txt").write_text("keep", encoding="utf-8")
    link: Final[Path] = purelib / "linked"
    run(["cmd", "/c", "mklink", "/J", str(link), str(target)], check=True, capture_output=True)
    (dist_info / "RECORD").write_text("linked,,\n", encoding="utf-8")
    CopyPipInstall._uninstall_dist(dist_info, env)  # ruff:ignore[private-member-access]  # metadata cleanup
    assert (link.exists(), (target / "keep.txt").read_text(encoding="utf-8")) == (False, "keep")


@pytest.mark.skipif(os.name != "nt", reason="Windows cloud reparse tags")
def test_seed_metadata_removes_cloud_directory_contents(tmp_path: Path, mocker: MockerFixture) -> None:
    dist_info: Final[Path] = tmp_path / "seed-0.dist-info"
    dist_info.mkdir()
    cloud: Final[Path] = tmp_path / "cloud"
    cloud.mkdir()
    (cloud / "module.py").touch()
    (dist_info / "RECORD").write_text("cloud,,\n", encoding="utf-8")
    original_lstat = Path.lstat

    def cloud_lstat(path: Path) -> os.stat_result:
        info = original_lstat(path)
        if path == cloud:
            # IO_REPARSE_TAG_CLOUD has no name-surrogate bit.
            return os.stat_result(info, {"st_reparse_tag": 0x9000001A, "st_file_attributes": 0x410})
        return info

    mocker.patch.object(Path, "lstat", side_effect=cloud_lstat, autospec=True)
    CopyPipInstall._uninstall_dist(dist_info, tmp_path)  # ruff:ignore[private-member-access]  # metadata cleanup
    assert (cloud.exists(), dist_info.exists()) == (False, False)


def test_seed_package_installs_do_not_overlap(tmp_path: Path, mocker: MockerFixture) -> None:
    ready: Final[Barrier] = Barrier(2)
    overlap: Final[Barrier] = Barrier(2)
    concurrent: Final[list[CopyPipInstall]] = []

    def build_image(*_args: object) -> None:
        ready.wait(timeout=5)

    def install(installer: CopyPipInstall, _version_info: tuple[int, ...]) -> None:
        try:
            overlap.wait(timeout=1)
        except BrokenBarrierError:
            return
        concurrent.append(installer)

    mocker.patch(
        "virtualenv.seed.embed.via_app_data.via_app_data._build_wheel_image", side_effect=build_image, autospec=True
    )
    installed = mocker.patch.object(CopyPipInstall, "install", side_effect=install, autospec=True)
    cli_run(
        [str(tmp_path / "env"), "--no-periodic-update", "--pip", "bundle", "--setuptools", "bundle"],
        setup_logging=False,
    )
    assert (installed.call_count, concurrent) == (2, [])


@pytest.mark.parametrize(
    "linked",
    [
        pytest.param(False, id="copy"),
        pytest.param(
            True, id="symlink", marks=pytest.mark.skipif(not fs_supports_symlink(), reason="symlinks are unavailable")
        ),
    ],
)
def test_seed_metadata_keeps_reseeding_supported(
    tmp_path: Path, linked: bool, caplog: pytest.LogCaptureFixture
) -> None:
    args: Final[list[str]] = [
        str(tmp_path / "env"),
        "--pip",
        "embed",
        "--no-periodic-update",
        *{True: ["--symlink-app-data"], False: []}[linked],
    ]
    cli_run(args, setup_logging=False)
    session: Final[Session] = cli_run(args, setup_logging=False)
    package: Final[Path] = session.creator.purelib / "pip"
    assert ((package / "__init__.py").is_file(), package.is_symlink(), "skip removal of" in caplog.text) == (
        True,
        linked,
        False,
    )


@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="requires FIFOs")
@pytest.mark.parametrize("metadata_file", ["top_level.txt", "RECORD"])
def test_seed_metadata_skips_fifo(no_seed_session: Session, tmp_path: Path, metadata_file: str) -> None:
    dist_info: Final[Path] = no_seed_session.creator.purelib / "pip-0.dist-info"
    dist_info.mkdir()
    os.mkfifo(dist_info / metadata_file)
    result = run(
        [
            sys.executable,
            "-m",
            "virtualenv",
            str(no_seed_session.creator.dest),
            "--app-data",
            str(tmp_path / "cache"),
            "--no-periodic-update",
            "--no-setuptools",
        ],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert (
        result.returncode,
        "not a regular file" in result.stdout,
        dist_info.exists(),
        (no_seed_session.creator.purelib / "pip" / "__init__.py").is_file(),
    ) == (0, True, False, True)


@pytest.mark.skipif(os.name == "nt", reason="requires POSIX non-blocking files")
def test_seed_metadata_is_read_without_blocking(tmp_path: Path, mocker: MockerFixture) -> None:
    metadata: Final[Path] = tmp_path / "RECORD"
    metadata.write_text("seed.py,,", encoding="utf-8")
    original_fstat = os.fstat
    blocking: list[bool] = []

    def fstat(fd: int) -> os.stat_result:
        blocking.append(os.get_blocking(fd))
        return original_fstat(fd)

    mocker.patch.object(os, "fstat", side_effect=fstat, autospec=True)
    content = PipInstall._read_regular_metadata(metadata)  # ruff:ignore[private-member-access]  # open descriptor
    assert (content, blocking) == ("seed.py,,", [False])


@pytest.mark.skipif(os.name == "nt" or not fs_supports_symlink(), reason="requires POSIX device links")
@pytest.mark.parametrize("metadata_file", ["top_level.txt", "RECORD"])
def test_seed_metadata_skips_device(
    no_seed_session: Session, tmp_path: Path, caplog: pytest.LogCaptureFixture, metadata_file: str
) -> None:
    dist_info: Final[Path] = no_seed_session.creator.purelib / "pip-0.dist-info"
    dist_info.mkdir()
    (dist_info / metadata_file).symlink_to(os.devnull)
    cli_run(
        [str(no_seed_session.creator.dest), "--app-data", str(tmp_path / "cache"), "--no-periodic-update"],
        setup_logging=False,
    )
    assert (
        "not a regular file" in caplog.text,
        dist_info.exists(),
        (no_seed_session.creator.purelib / "pip" / "__init__.py").is_file(),
    ) == (True, False, True)


@pytest.mark.skipif(not fs_supports_symlink(), reason="requires symlinks")
@pytest.mark.parametrize(
    ("metadata_file", "content"),
    [
        pytest.param("top_level.txt", "stale.py\n", id="top-level"),
        pytest.param("RECORD", "stale.py,,\n", id="record"),
    ],
)
def test_seed_metadata_reads_linked_file(
    no_seed_session: Session, tmp_path: Path, metadata_file: str, content: str
) -> None:
    purelib: Final[Path] = no_seed_session.creator.purelib
    dist_info: Final[Path] = purelib / "pip-0.dist-info"
    dist_info.mkdir()
    stale: Final[Path] = purelib / "stale.py"
    stale.write_text("old", encoding="utf-8")
    target: Final[Path] = tmp_path / "metadata.txt"
    target.write_text(content, encoding="utf-8")
    (dist_info / metadata_file).symlink_to(target)
    cli_run([str(no_seed_session.creator.dest), "--no-periodic-update"], setup_logging=False)
    assert (stale.exists(), target.read_text(encoding="utf-8"), dist_info.exists()) == (False, content, False)


@pytest.mark.skipif(not fs_supports_symlink(), reason="symlinks are unavailable")
def test_seed_metadata_keeps_empty_folder_behind_symlink(tmp_path: Path) -> None:
    args: Final[list[str]] = [str(tmp_path / "env"), "--pip", "embed", "--no-periodic-update"]
    session: Final[Session] = cli_run(args, setup_logging=False)
    outside: Final[Path] = tmp_path / "outside" / "empty"
    outside.mkdir(parents=True)
    (session.creator.purelib / "linked").symlink_to(outside.parent, target_is_directory=True)
    record: Final[Path] = next(session.creator.purelib.glob("pip-*.dist-info")) / "RECORD"
    record.write_text(f"{record.read_text(encoding='utf-8')}\nlinked/empty/gone.txt,,", encoding="utf-8")
    cli_run(args, setup_logging=False)
    assert outside.is_dir()


def test_seed_metadata_keeps_bytecode_of_dotted_module(tmp_path: Path) -> None:
    args: Final[list[str]] = [str(tmp_path / "env"), "--pip", "embed", "--no-periodic-update"]
    session: Final[Session] = cli_run(args, setup_logging=False)
    cache: Final[Path] = session.creator.purelib / "__pycache__"
    cache.mkdir(exist_ok=True)
    (session.creator.purelib / "foo.py").write_text("", encoding="utf-8")
    own: Final[list[Path]] = [cache / "foo.cpython-314.pyc", cache / "foo.cpython-314.opt-1.pyc"]
    other: Final[Path] = cache / "foo.bar.cpython-314.pyc"
    for path in [*own, other]:
        path.write_bytes(b"")
    record: Final[Path] = next(session.creator.purelib.glob("pip-*.dist-info")) / "RECORD"
    record.write_text(f"{record.read_text(encoding='utf-8')}\nfoo.py,,", encoding="utf-8")
    cli_run(args, setup_logging=False)
    assert (other.exists(), [path.exists() for path in own]) == (True, [False, False])


@pytest.mark.usefixtures("_no_coverage")
@pytest.mark.parametrize(
    ("install_args", "run_args"),
    [
        pytest.param([], [], id="compiled"),
        pytest.param(["--no-compile"], [], id="no-compile-then-run"),
        pytest.param([], ["-O"], id="optimized-run"),
    ],
)
@pytest.mark.parametrize(
    "linked",
    [
        pytest.param(False, id="copy"),
        pytest.param(
            True, id="symlink", marks=pytest.mark.skipif(not fs_supports_symlink(), reason="symlinks are unavailable")
        ),
    ],
)
def test_reseed_over_pip_installed_by_pip(
    tmp_path: Path, linked: bool, install_args: list[str], run_args: list[str]
) -> None:
    args: Final[list[str]] = [
        str(tmp_path / "env"),
        "--pip",
        "embed",
        "--no-setuptools",
        "--no-periodic-update",
        *{True: ["--symlink-app-data"], False: []}[linked],
    ]
    session: Final[Session] = cli_run(args, setup_logging=False)
    version: Final[str] = next(session.creator.purelib.glob("pip-*.dist-info")).stem.split("-")[1]
    # a wheel pip installs has no top_level.txt and a RECORD of files only
    check_call([
        str(session.creator.exe),
        "-m",
        "pip",
        "install",
        "-q",
        "--disable-pip-version-check",
        "--force-reinstall",
        *install_args,
        "--no-index",
        "--find-links",
        str(BUNDLE_FOLDER),
        f"pip=={version}",
    ])
    # running pip writes bytecode RECORD does not list
    check_call([str(session.creator.exe), *run_args, "-m", "pip", "--version"])
    package: Final[Path] = cli_run(args, setup_logging=False).creator.purelib / "pip"
    assert ((package / "__init__.py").is_file(), package.is_symlink()) == (True, linked)


@pytest.mark.usefixtures("_no_coverage")
@pytest.mark.skipif(os.name != "nt", reason="Windows refuses to delete read-only files")
def test_reseed_over_read_only_environment(tmp_path: Path) -> None:
    args: Final[list[str]] = [str(tmp_path / "env"), "--copies", "--pip", "embed", "--no-periodic-update"]
    dest: Final[Path] = cli_run(args, setup_logging=False).creator.dest
    # chmod follows a link on newer Pythons and would mark the base interpreter read-only
    for path in (entry for entry in dest.rglob("*") if entry.is_file() and not entry.is_symlink()):
        path.chmod(S_IREAD)
    session: Final[Session] = cli_run(args, setup_logging=False)
    assert (session.creator.purelib / "pip" / "__init__.py").is_file()


_QUOTING_ONLY: Final[pytest.MarkDecorator] = pytest.mark.skipif(
    IS_PYPY or IS_GRAALPY, reason="quoting does not depend on the interpreter, the CPython jobs run this matrix"
)


@pytest.mark.parametrize(
    "name",
    [
        # GraalPy skips the slow launcher tests, so the plain case is its only check that a console script runs
        pytest.param(
            "plain", id="plain", marks=pytest.mark.skipif(IS_PYPY, reason="the slow app-data seed test runs a launcher")
        ),
        pytest.param("two words", id="space", marks=_QUOTING_ONLY),
        pytest.param("owner's env", id="apostrophe", marks=_QUOTING_ONLY),
        pytest.param("$(echo a) `echo b`", id="command-substitution", marks=_QUOTING_ONLY),
        pytest.param(
            "a" * 120,
            id="long",
            marks=[_QUOTING_ONLY, pytest.mark.skipif(os.name == "nt", reason="POSIX shebang limit")],
        ),
        pytest.param(
            "env \\path",
            id="backslash",
            marks=[_QUOTING_ONLY, pytest.mark.skipif(os.name == "nt", reason="POSIX filename")],
        ),
        pytest.param(
            "env\tname", id="tab", marks=[_QUOTING_ONLY, pytest.mark.skipif(os.name == "nt", reason="POSIX filename")]
        ),
    ],
)
@pytest.mark.parametrize(
    "via_python",
    [
        pytest.param(False, id="launcher"),
        pytest.param(
            True, id="python", marks=pytest.mark.skipif(os.name == "nt", reason="Windows launcher is an executable")
        ),
    ],
)
@pytest.mark.parametrize("seeder", [pytest.param("app-data", id="app-data"), pytest.param("pip", id="pip")])
def test_console_script_preserves_interpreter_path(
    tmp_path: Path, current_fastest: str, name: str, via_python: bool, seeder: str
) -> None:
    destination: Final[str] = os.path.join(str(tmp_path), name, "env")
    # GraalPy on a busy macOS runner takes over a minute to create and seed an environment, so the timeouts only guard
    # against a hang.
    run(
        [
            sys.executable,
            "-m",
            "virtualenv",
            destination,
            "--seeder",
            seeder,
            "--creator",
            current_fastest,
            "--activators",
            "",
            "--no-periodic-update",
            "--pip",
            "embed",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=300,
        check=True,
    )
    scripts: Final[str] = os.path.join(destination, _SCRIPTS_DIR)
    result: Final[CompletedProcess[str]] = run(
        [
            *{True: [os.path.join(scripts, "python")], False: []}[via_python],
            os.path.join(scripts, _PIP_EXE),
            "--version",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
        check=True,
    )
    assert os.path.normcase(destination) in os.path.normcase(result.stdout)


@pytest.mark.skipif(os.name != "posix", reason="POSIX shebangs")
@pytest.mark.parametrize("seeder", [pytest.param("app-data", id="app-data"), pytest.param("pip", id="pip")])
@pytest.mark.parametrize(
    "name",
    [
        pytest.param("rock'n'roll", id="apostrophe"),
        pytest.param('double"quote"', id="double-quote"),
        pytest.param("back\\slash", id="backslash"),
    ],
)
def test_console_script_runs_after_xonsh_shebang_parse(tmp_path: Path, seeder: str, name: str) -> None:
    session: Final[Session] = cli_run([
        str(tmp_path / name / "env"),
        "--seeder",
        seeder,
        "--pip",
        "embed",
        "--no-download",
        "--no-periodic-update",
        "--app-data",
        str(tmp_path / "cache"),
        "--activators",
        "",
    ])
    script: Final[Path] = session.creator.script("pip")
    interpreter: Final[list[str]] = shlex.split(os.fsdecode(script.read_bytes().split(b"\n", 1)[0][2:]))
    result: Final[CompletedProcess[str]] = run(
        [*interpreter, str(script), "--version"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
        check=True,
    )
    assert str(session.creator.dest) in result.stdout


@pytest.mark.slow
@pytest.mark.parametrize("copies", [False, True] if fs_supports_symlink() else [True])
def test_seed_link_via_app_data(tmp_path, coverage_env, current_fastest, copies) -> None:
    current = PythonInfo.current_system()
    bundle_ver = BUNDLE_SUPPORT[current.version_release_str]
    create_cmd = [
        str(tmp_path / "en v"),  # space in the name to ensure generated scripts work when path has space
        "--no-periodic-update",
        "--seeder",
        "app-data",
        "--extra-search-dir",
        str(BUNDLE_FOLDER),
        "--download",
        "--pip",
        bundle_ver["pip"].split("-")[1],
        "--setuptools",
        bundle_ver["setuptools"].split("-")[1],
        "--reset-app-data",
        "--creator",
        current_fastest,
        "-vv",
        *{True: [], False: ["--symlink-app-data"]}[copies],
    ]
    result = cli_run(create_cmd)
    coverage_env()
    assert result

    # uninstalling pip/setuptools now should leave us with a ensure_safe_to_do env
    site_package = result.creator.purelib
    pip = site_package / "pip"
    setuptools = site_package / "setuptools"

    files_post_first_create = set(site_package.iterdir())
    assert pip in files_post_first_create
    assert setuptools in files_post_first_create
    for pip_exe in [
        result.creator.script_dir / f"pip{suffix}{result.creator.exe.suffix}"
        for suffix in (
            "",
            f"{current.version_info.major}",
            f"{current.version_info.major}.{current.version_info.minor}",
            f"-{current.version_info.major}.{current.version_info.minor}",
        )
    ]:
        assert pip_exe.exists()
        process = Popen([str(pip_exe), "--version", "--disable-pip-version-check"])
        _, __ = process.communicate()
        assert not process.returncode

    remove_cmd = [
        str(result.creator.script("pip")),
        "--verbose",
        "--disable-pip-version-check",
        "uninstall",
        "-y",
        "setuptools",
    ]
    process = Popen(remove_cmd)
    _, __ = process.communicate()
    assert not process.returncode
    assert site_package.exists()

    files_post_first_uninstall = set(site_package.iterdir())
    assert pip in files_post_first_uninstall
    assert setuptools not in files_post_first_uninstall

    # install a different setuptools to test that virtualenv removes this before installing new; a local stub keeps
    # the test off the network, where an index outage would fail it
    (stub_dir := tmp_path / "stub").mkdir()
    stub_files: Final[dict[str, str]] = {
        "setuptools/__init__.py": "",
        "setuptools-0.1.dist-info/METADATA": "Metadata-Version: 2.1\nName: setuptools\nVersion: 0.1\n",
        "setuptools-0.1.dist-info/WHEEL": "Wheel-Version: 1.0\nRoot-Is-Purelib: true\nTag: py3-none-any\n",
        "setuptools-0.1.dist-info/top_level.txt": "setuptools\n",
    }
    with zipfile.ZipFile(stub_dir / "setuptools-0.1-py3-none-any.whl", "w") as stub:
        for name, content in stub_files.items():
            stub.writestr(name, content)
        stub.writestr("setuptools-0.1.dist-info/RECORD", "".join(f"{name},,\n" for name in stub_files))
    process = Popen([
        str(result.creator.script("pip")),
        "--verbose",
        "--disable-pip-version-check",
        "install",
        "--no-index",
        "--find-links",
        str(stub_dir),
        "setuptools==0.1",
    ])
    process.communicate()
    assert not process.returncode
    assert site_package.exists()
    files_post_downgrade = set(site_package.iterdir())
    assert setuptools in files_post_downgrade

    # check we can run it again and will work - checks both overwrite and reuse cache
    result = cli_run(create_cmd)
    coverage_env()
    assert result
    files_post_second_create = set(site_package.iterdir())
    assert files_post_first_create == files_post_second_create

    # Windows does not allow removing a executable while running it, so when uninstalling pip we need to do it via
    # python -m pip
    remove_cmd = [str(result.creator.exe), "-m", "pip", *remove_cmd[1:]]
    process = Popen([*remove_cmd, "pip", "wheel"])
    _, __ = process.communicate()
    assert not process.returncode
    # pip is greedy here, removing all packages removes the site-package too
    purelib = result.creator.purelib
    patch_files = {purelib / f"{'_virtualenv'}.{i}" for i in ("py", "pyc", "pth")}
    patch_files.add(purelib / "__pycache__")
    post_run = set(site_package.glob("*")) - patch_files
    assert not post_run, "\n".join(str(i) for i in post_run)


@pytest.fixture
def read_only_app_data(temp_app_data):
    temp_app_data.mkdir()
    with read_only_dir(temp_app_data):
        yield temp_app_data


@contextlib.contextmanager
def read_only_dir(directory):
    write = S_IWUSR | S_IWGRP | S_IWOTH
    for root, _, filenames in os.walk(str(directory)):
        os.chmod(root, os.stat(root).st_mode & ~write)
        for filename in filenames:
            name = os.path.join(root, filename)
            os.chmod(name, os.stat(name).st_mode & ~write)
    try:
        yield
    finally:
        for root, _, filenames in os.walk(str(directory)):
            os.chmod(root, os.stat(root).st_mode | write)
            for filename in filenames:
                name = os.path.join(root, filename)
                os.chmod(name, os.stat(name).st_mode | write)


@pytest.mark.skipif(sys.platform == "win32", reason="Windows only applies R/O to files")
def test_read_only_app_data_reuses_extracted_embed_wheel(temp_app_data: Path) -> None:
    wheel: Final[Path] = get_embed_wheel("pip", f"{sys.version_info.major}.{sys.version_info.minor}").path
    (unzip := temp_app_data / "unzip" / __version__).mkdir(parents=True)
    copy2(wheel, unzip / wheel.name)
    app_data: Final[ReadOnlyAppData] = ReadOnlyAppData(str(temp_app_data))

    # this is how a zipapp makes its embedded wheels available, see ensure_extracted
    with read_only_dir(temp_app_data), app_data.extract(wheel, None) as extracted:
        assert extracted == unzip / wheel.name


@pytest.mark.slow
@pytest.mark.skipif(sys.platform == "win32", reason="Windows only applies R/O to files")
@pytest.mark.usefixtures("read_only_app_data")
def test_base_bootstrap_link_via_app_data_not_writable(tmp_path, current_fastest) -> None:
    result = cli_run(["--seeder", "app-data", "--creator", current_fastest, "-vv", str(tmp_path / "venv")])
    assert result


@pytest.mark.slow
@pytest.mark.skipif(sys.platform == "win32", reason="Windows only applies R/O to files")
def test_populated_read_only_cache_and_symlinked_app_data(tmp_path, current_fastest, temp_app_data) -> None:
    dest = tmp_path / "venv"
    cmd = [
        "--seeder",
        "app-data",
        "--creator",
        current_fastest,
        "--symlink-app-data",
        "-vv",
        str(dest),
    ]

    assert cli_run(cmd)
    check_call((str(dest.joinpath("bin/python")), "-c", "import pip"))

    cached_py_info._CACHE.clear()  # ruff:ignore[private-member-access]  # preserve the disk cache for the read-only test
    safe_delete(dest)

    # should succeed with special flag when read-only
    with read_only_dir(temp_app_data):
        assert cli_run(["--read-only-app-data", *cmd])
        check_call((str(dest.joinpath("bin/python")), "-c", "import pip"))


@pytest.mark.slow
@pytest.mark.skipif(sys.platform == "win32", reason="Windows only applies R/O to files")
def test_populated_read_only_cache_and_copied_app_data(tmp_path, current_fastest, temp_app_data) -> None:
    dest = tmp_path / "venv"
    cmd = [
        "--seeder",
        "app-data",
        "--creator",
        current_fastest,
        "-vv",
        "-p",
        "python",
        str(dest),
    ]

    assert cli_run(cmd)

    cached_py_info._CACHE.clear()  # ruff:ignore[private-member-access]  # preserve the disk cache for the read-only test
    safe_delete(dest)

    # should succeed with special flag when read-only
    with read_only_dir(temp_app_data):
        assert cli_run(["--read-only-app-data", *cmd])


@pytest.mark.skipif(os.name != "posix" or os.geteuid() == 0, reason="directory permissions that bind the current user")
@pytest.mark.skipif(not fs_supports_symlink(), reason="symlinks are unavailable")
def test_linked_seed_image_refuses_writes_and_can_be_reset(tmp_path: Path, temp_app_data: Path) -> None:
    arguments: Final[list[str]] = ["--symlink-app-data", "--activators", "", str(tmp_path / "venv")]
    linked: Final[Path] = cli_run(arguments).creator.purelib / "pip" / "__init__.py"
    image: Final[Path] = linked.resolve()

    with pytest.raises(PermissionError):
        linked.unlink()

    cli_run(["--reset-app-data", *arguments])
    assert (image.exists(), linked.resolve() == image, any(temp_app_data.rglob("*.dist-info"))) == (True, True, True)


@pytest.mark.skipif(os.name != "posix", reason="POSIX file permission bits")
@pytest.mark.usefixtures("temp_app_data")
def test_copied_seed_is_writable_from_read_only_image(tmp_path: Path, temp_app_data: Path) -> None:
    copied: Final[Path] = cli_run(["--activators", "", str(tmp_path / "venv")]).creator.purelib / "pip"
    image: Final[Path] = next(temp_app_data.rglob("CopyPipInstall/*/pip"))

    modes: Final[list[int]] = [
        path.stat().st_mode & 0o222 for path in (image, image / "__init__.py", copied, copied / "__init__.py")
    ]
    assert modes == [0, 0, 0o200, 0o200]


@pytest.mark.slow
@pytest.mark.parametrize("pkg", ["pip", "setuptools"])
@pytest.mark.usefixtures("session_app_data", "current_fastest", "coverage_env")
def test_base_bootstrap_link_via_app_data_no(tmp_path, pkg) -> None:
    result = cli_run([str(tmp_path), "--seeder", "app-data", f"--no-{pkg}", "--setuptools", "bundle"])
    assert not (result.creator.purelib / pkg).exists()
    for key in {"pip", "setuptools"} - {pkg}:
        assert (result.creator.purelib / key).exists()


@pytest.mark.usefixtures("temp_app_data")
def test_app_data_parallel_ok(tmp_path) -> None:
    exceptions = _run_parallel_threads(tmp_path)
    assert not exceptions, "\n".join(exceptions)


def _run_parallel_threads(tmp_path):
    exceptions = []

    def _run(name) -> None:
        try:
            cli_run(["--seeder", "app-data", str(tmp_path / name), "--no-setuptools"])
        # every seeder failure is collected, so the test asserts on all of them together
        except Exception as exception:  # ruff:ignore[blind-except]
            exceptions.append(str(exception))

    threads = [Thread(target=_run, args=(f"env{i}",)) for i in range(1, 3)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    return exceptions


@pytest.mark.usefixtures("temp_app_data")
def test_app_data_parallel_fail(tmp_path: Path, mocker: MockerFixture) -> None:
    mocker.patch(
        "virtualenv.seed.embed.via_app_data.pip_install.base.PipInstall.build_image",
        side_effect=RuntimeError,
        autospec=True,
    )
    exceptions = _run_parallel_threads(tmp_path)
    assert len(exceptions) == 2
    for exception in exceptions:
        assert exception.startswith("failed to build image pip because:\nTraceback")
        assert "RuntimeError" in exception, exception


@pytest.mark.usefixtures("temp_app_data")
def test_seed_reports_wheel_lookup_failure(
    tmp_path: Path, mocker: MockerFixture, caplog: pytest.LogCaptureFixture
) -> None:
    mocker.patch(
        "virtualenv.seed.embed.via_app_data.via_app_data.get_wheel",
        side_effect=RuntimeError("lookup offline"),
        autospec=True,
    )

    with pytest.raises(RuntimeError, match="seed failed due to failing to download wheels pip"):
        cli_run([str(tmp_path / "env"), "--no-setuptools", "--no-periodic-update"], setup_logging=False)

    assert "lookup offline" in caplog.text


_DISK_FULL: Final[OSError] = OSError(errno.ENOSPC, "No space left on device")


def _fail_during_extraction(zip_ref: zipfile.ZipFile, target_dir: Path) -> None:
    # stop short of the last entries, where the wheel keeps its dist-info files
    for info in zip_ref.infolist()[:-5]:
        zip_ref.extract(info, str(target_dir))
    raise _DISK_FULL


@pytest.mark.parametrize(
    ("target", "failure", "linked"),
    [
        pytest.param("base.extract_zip", _fail_during_extraction, False, id="copy-extract"),
        pytest.param("base.PipInstall._generate_new_files", _DISK_FULL, False, id="copy-finish"),
        pytest.param(
            "base.extract_zip",
            _fail_during_extraction,
            True,
            id="symlink-extract",
            marks=pytest.mark.skipif(not fs_supports_symlink(), reason="symlinks are unavailable"),
        ),
        pytest.param(
            "base.PipInstall._generate_new_files",
            _DISK_FULL,
            True,
            id="symlink-finish",
            marks=pytest.mark.skipif(not fs_supports_symlink(), reason="symlinks are unavailable"),
        ),
        pytest.param(
            "symlink.set_tree",
            _DISK_FULL,
            True,
            id="symlink-read-only",
            marks=pytest.mark.skipif(not fs_supports_symlink(), reason="symlinks are unavailable"),
        ),
    ],
)
def test_seed_image_build_failure_leaves_no_partial_image(
    tmp_path: Path,
    mocker: MockerFixture,
    target: str,
    failure: Callable[[zipfile.ZipFile, Path], None] | OSError,
    linked: bool,
) -> None:
    cache: Final[Path] = tmp_path / "cache"
    args: Final[list[str]] = [
        str(tmp_path / "env"),
        "--app-data",
        str(cache),
        "--no-periodic-update",
        "--no-setuptools",
        *{True: ["--symlink-app-data"], False: []}[linked],
    ]
    patched: Final[MockType] = mocker.patch(
        f"virtualenv.seed.embed.via_app_data.pip_install.{target}", side_effect=failure, autospec=True
    )
    with pytest.raises(RuntimeError, match="No space left on device"):
        cli_run(args, setup_logging=False)
    mocker.stop(patched)
    installer: Final[str] = {True: "SymlinkPipInstall", False: "CopyPipInstall"}[linked]
    images: Final[Path] = next(cache.glob("wheel/*/image/1"))
    left: Final[list[str]] = sorted(i.name for i in [*images.iterdir(), *(images / installer).iterdir()] if i.is_dir())
    purelib: Final[Path] = cli_run(args, setup_logging=False).creator.purelib
    dist_info: Final[Path] = next(purelib.glob("pip-*.dist-info"))
    assert (
        left,
        (dist_info / "INSTALLER").is_file(),
        (dist_info / "RECORD").is_file(),
        (purelib / f"{dist_info.stem}.virtualenv").is_file(),
    ) == ([installer], True, True, True)


@pytest.mark.parametrize(
    ("leftover", "files", "kept"),
    [
        pytest.param("CopyPipInstall-{}", ("pip.py",), False, id="killed-build"),
        pytest.param("CopyPipInstall/{}", (), True, id="empty-image"),
    ],
)
def test_seed_image_build_replaces_leftovers(tmp_path: Path, leftover: str, files: tuple[str, ...], kept: bool) -> None:
    cache: Final[Path] = tmp_path / "cache"
    version: Final[str] = PythonInfo.current_system().version_release_str
    path: Final[Path] = (
        cache / "wheel" / version / "image" / "1" / leftover.format(BUNDLE_SHA256[BUNDLE_SUPPORT[version]["pip"]])
    )
    path.mkdir(parents=True)
    for name in files:
        (path / name).write_text("", encoding="utf-8")
    args: Final[list[str]] = [
        str(tmp_path / "env"),
        "--app-data",
        str(cache),
        "--no-periodic-update",
        "--no-setuptools",
    ]
    purelib: Final[Path] = cli_run([*args, "--pip", "embed"], setup_logging=False).creator.purelib
    assert (path.exists(), (next(purelib.glob("pip-*.dist-info")) / "RECORD").is_file()) == (kept, True)


def test_seed_image_uses_selected_wheel_contents(tmp_path: Path) -> None:
    def seed(build: str) -> str:
        with zipfile.ZipFile(tmp_path / "pip-99-py3-none-any.whl", "w") as archive:
            archive.writestr("pip-99.dist-info/METADATA", "Name: pip\nVersion: 99\n")
            archive.writestr("pip-99.dist-info/RECORD", "")
            archive.writestr("build.txt", build)
        session = cli_run([
            str(tmp_path / build),
            "--app-data",
            str(tmp_path / "cache"),
            "--extra-search-dir",
            str(tmp_path),
            "--pip",
            "99",
            "--no-periodic-update",
            "--no-setuptools",
        ])
        return (session.creator.purelib / "build.txt").read_text(encoding="utf-8")

    assert (seed("first"), seed("second")) == ("first", "second")


def test_seed_image_build_direct_call(tmp_path: Path) -> None:
    session: Final[Session] = cli_run([str(tmp_path / "env"), "--no-seed"], setup_logging=False)
    wheel: Final[Path] = BUNDLE_FOLDER / BUNDLE_SUPPORT[session.interpreter.version_release_str]["pip"]
    image: Final[Path] = tmp_path / "image" / "CopyPipInstall" / wheel.stem
    installer: Final[CopyPipInstall] = CopyPipInstall(wheel, session.creator, image)
    installer.build_image()
    installer.install(session.interpreter.version_info)
    assert (
        sorted(i.name for i in image.parent.parent.iterdir()),
        (next(image.glob("*.dist-info")) / "INSTALLER").is_file(),
        session.creator.script("pip").exists(),
    ) == (["CopyPipInstall"], True, True)


def test_seed_image_without_metadata_fails(no_seed_session: Session, tmp_path: Path) -> None:
    image = tmp_path / "image"
    image.mkdir()
    (image / "unexpected").touch()
    installer = CopyPipInstall(tmp_path / "example-1-py3-none-any.whl", no_seed_session.creator, image)

    with pytest.raises(RuntimeError, match=r"no \.dist-info at .*image, has unexpected"):
        installer.install(no_seed_session.interpreter.version_info)


@pytest.mark.parametrize(
    "ending", [pytest.param(b"", id="no-newline"), pytest.param(b"\n", id="lf"), pytest.param(b"\r\n", id="crlf")]
)
def test_copy_seed_preserves_record_rows(tmp_path: Path, copy_seed_record: tuple[Path, list[list[str]]]) -> None:
    session: Final[Session] = cli_run([str(tmp_path / "env"), "--no-seed"], setup_logging=False)
    wheel, original_rows = copy_seed_record
    image: Final[Path] = tmp_path / "image" / "CopyPipInstall" / wheel.stem
    installer: Final[CopyPipInstall] = CopyPipInstall(wheel, session.creator, image)
    installer.build_image()
    installer.install(session.interpreter.version_info)

    dist_info: Final[Path] = next(session.creator.purelib.glob("pip-*.dist-info"))
    with (dist_info / "RECORD").open(encoding="utf-8", newline="") as stream:
        rows = list(csv.reader(stream))
    assert rows[: len(original_rows)] == original_rows
    files: Final[list[PackagePath] | None] = PathDistribution(dist_info).files
    assert files is not None
    assert f"{dist_info.name}/INSTALLER" in {Path(file).as_posix() for file in files}


@pytest.fixture(
    params=[
        pytest.param("data,one.py", id="comma"),
        pytest.param(
            'data"one.py', id="quote", marks=pytest.mark.skipif(os.name == "nt", reason="unsupported filename")
        ),
        pytest.param("data\none.py", id="lf", marks=pytest.mark.skipif(os.name == "nt", reason="unsupported filename")),
        pytest.param("data\rone.py", id="cr", marks=pytest.mark.skipif(os.name == "nt", reason="unsupported filename")),
    ]
)
def record_filename(request: pytest.FixtureRequest) -> str:
    return request.param


def test_seed_uninstall_reads_quoted_record_paths(
    tmp_path: Path, no_seed_session: Session, record_filename: str
) -> None:
    purelib = no_seed_session.creator.purelib
    dist_info = purelib / "example-1.0.dist-info"
    dist_info.mkdir(parents=True)
    installed = purelib / record_filename
    installed.write_text("old package data", encoding="utf-8")
    unrelated = purelib / "keep.py"
    unrelated.write_text("keep", encoding="utf-8")
    with (dist_info / "RECORD").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow([record_filename, "", ""])
        writer.writerow([f"{dist_info.name}/RECORD", "", ""])

    image = tmp_path / "image"
    new_dist_info = image / "example-2.0.dist-info"
    new_dist_info.mkdir(parents=True)
    (new_dist_info / "RECORD").touch()
    installer = CopyPipInstall(tmp_path / "example-2.0-py3-none-any.whl", no_seed_session.creator, image)
    installer.install(no_seed_session.interpreter.version_info)

    assert (installed.exists(), dist_info.exists(), unrelated.read_text(encoding="utf-8")) == (False, False, "keep")


def test_seed_uninstall_does_not_look_up_outside_metadata_paths(
    tmp_path: Path, no_seed_session: Session, mocker: MockerFixture
) -> None:
    env_dir = no_seed_session.creator.dest
    purelib = no_seed_session.creator.purelib
    dist_info = purelib / "pip-0.dist-info"
    dist_info.mkdir()
    inside = env_dir / "old.py"
    inside.write_text("old", encoding="utf-8")
    outside = tmp_path / "outside.py"
    outside.write_text("keep", encoding="utf-8")
    outside_relative = os.path.relpath(outside, purelib)
    (dist_info / "RECORD").write_text(
        f"{outside},,\n{outside_relative},,\n{os.path.relpath(inside, purelib)},,\n", encoding="utf-8"
    )
    (dist_info / "top_level.txt").write_text(f"{outside}\n{outside_relative}\n", encoding="utf-8")
    exists = Path.exists
    glob = Path.glob

    def checked_exists(path: Path) -> bool:
        assert Path(os.path.abspath(path)) != outside
        return exists(path)

    def checked_glob(path: Path, pattern: str) -> Iterator[Path]:
        assert Path(os.path.abspath(path)) != outside.parent / "__pycache__"
        return glob(path, pattern)

    mocker.patch.object(Path, "exists", checked_exists)
    mocker.patch.object(Path, "glob", checked_glob)
    cli_run([str(env_dir), "--no-periodic-update", "--no-setuptools"], setup_logging=False)

    assert (inside.exists(), outside.read_text(encoding="utf-8"), dist_info.exists()) == (False, "keep", False)


@pytest.fixture
def wheel_with_record_filename(tmp_path: Path, no_seed_session: Session, record_filename: str) -> Path:
    bundled = BUNDLE_FOLDER / BUNDLE_SUPPORT[no_seed_session.interpreter.version_release_str]["pip"]
    wheel = tmp_path / bundled.name
    row = io.StringIO(newline="")
    csv.writer(row).writerow([record_filename, "", ""])
    with zipfile.ZipFile(bundled) as source, zipfile.ZipFile(wheel, "w") as target:
        for info in source.infolist():
            content = source.read(info)
            if info.filename.endswith(".dist-info/RECORD"):
                content += row.getvalue().encode("utf-8")
            target.writestr(info, content)
        target.writestr(record_filename, "value = 42\n")
    return wheel


@pytest.mark.parametrize(
    "installer_class",
    [
        pytest.param(CopyPipInstall, id="copy"),
        pytest.param(
            SymlinkPipInstall,
            id="symlink",
            marks=pytest.mark.skipif(not fs_supports_symlink(), reason="requires symlinks"),
        ),
    ],
)
def test_seed_records_quote_generated_paths(
    tmp_path: Path,
    no_seed_session: Session,
    wheel_with_record_filename: Path,
    record_filename: str,
    installer_class: type[CopyPipInstall | SymlinkPipInstall],
) -> None:
    image = tmp_path / "image" / installer_class.__name__ / wheel_with_record_filename.stem
    installer = installer_class(wheel_with_record_filename, no_seed_session.creator, image)
    installer.build_image()
    installer.install(no_seed_session.interpreter.version_info)

    dist_info = next(no_seed_session.creator.purelib.glob("pip-*.dist-info"))
    with (dist_info / "RECORD").open(encoding="utf-8", newline="") as stream:
        rows = list(csv.reader(stream))
    names = {Path(row[0]).name for row in rows}
    compiled = {name for name in names if name.startswith(f"{record_filename[:-3]}.") and name.endswith(".pyc")}
    assert ({len(row) for row in rows}, record_filename in names, len(compiled)) == ({3}, True, 1)


@pytest.fixture
def copy_seed_record(tmp_path: Path, ending: bytes) -> tuple[Path, list[list[str]]]:
    bundled: Final[Path] = BUNDLE_FOLDER / BUNDLE_SUPPORT[PythonInfo.current_system().version_release_str]["pip"]
    wheel: Final[Path] = tmp_path / bundled.name
    original_rows: list[list[str]] = []
    with zipfile.ZipFile(bundled) as source, zipfile.ZipFile(wheel, "w") as target:
        for info in source.infolist():
            content = source.read(info)
            if info.filename.endswith(".dist-info/RECORD"):
                content = content.rstrip(b"\r\n") + ending
                original_rows = list(csv.reader(io.StringIO(content.decode("utf-8"))))
            target.writestr(info, content)

    return wheel, original_rows


@pytest.mark.skipif(sys.platform != "win32", reason="Windows path limits")
@pytest.mark.parametrize(
    "error", [pytest.param(FileNotFoundError, id="lookup-failed"), pytest.param(KeyboardInterrupt, id="interrupted")]
)
def test_seed_image_failed_short_path_cleans_staging(
    tmp_path: Path,
    mocker: MockerFixture,
    monkeypatch: pytest.MonkeyPatch,
    no_seed_session: Session,
    error: type[BaseException],
) -> None:
    image: Final[Path] = tmp_path / "image" / "CopyPipInstall" / "pkg"
    staging: Final[Path] = image.parent.with_name(f"{image.parent.name}-{image.name}")
    wheel: Final[Path] = tmp_path / "pkg.whl"
    with zipfile.ZipFile(wheel, "w") as archive:
        archive.writestr("f" * (260 - len(str(staging))), "payload")
    working: Final[Path] = tmp_path / "working"
    working.mkdir()
    (working / "keep.txt").write_text("keep", encoding="utf-8")
    monkeypatch.chdir(working)
    mocker.patch("virtualenv.util.path.get_short_path_name", autospec=True, side_effect=error("short path"))

    with pytest.raises(error, match="short path"):
        CopyPipInstall(wheel, no_seed_session.creator, image).build_image()

    assert (staging.exists(), (working / "keep.txt").read_text(encoding="utf-8")) == (False, "keep")


@pytest.mark.skipif(sys.platform != "win32", reason="Windows path limits")
def test_seed_image_failed_short_path_on_reuse(tmp_path: Path, mocker: MockerFixture, no_seed_session: Session) -> None:
    image: Final[Path] = tmp_path / "image"
    image.mkdir()
    (image / "content").touch()
    wheel: Final[Path] = tmp_path / "pkg.whl"
    with zipfile.ZipFile(wheel, "w") as archive:
        archive.writestr("f" * (260 - len(str(image))), "payload")
    mocker.patch("ctypes.windll.kernel32.GetShortPathNameW", autospec=True, return_value=0)

    with pytest.raises(OSError, match=r"\[WinError \d+\]"):
        CopyPipInstall(wheel, no_seed_session.creator, image).has_image()

    assert (image / "content").is_file()


@pytest.mark.skipif(sys.platform != "win32", reason="Windows path limits")
@pytest.mark.parametrize(
    ("entry", "shortened"),
    [
        pytest.param("{file}", 0, id="file-fits"),
        pytest.param("{file}f", 1, id="file-too-long"),
        pytest.param("{folder}/x", 0, id="dir-fits"),
        pytest.param("{folder}d/x", 1, id="dir-too-long"),
    ],
)
def test_seed_image_short_path_limits(
    tmp_path: Path, mocker: MockerFixture, no_seed_session: Session, entry: str, shortened: int
) -> None:
    image: Final[Path] = tmp_path / "image"
    image.mkdir()
    (image / "content").touch()
    # the longest file name that fits under MAX_PATH, which also counts the separator and the terminating null
    room: Final[int] = 258 - len(str(image))
    wheel: Final[Path] = tmp_path / "pkg.whl"
    with zipfile.ZipFile(str(wheel), "w") as archive:
        archive.writestr(entry.format(file="f" * room, folder="d" * (room - 12)), "payload")
    shorten: Final[MockType] = mocker.patch(
        "virtualenv.util.path.get_short_path_name", autospec=True, return_value=str(image)
    )
    assert (CopyPipInstall(wheel, no_seed_session.creator, image).has_image(), shorten.call_count) == (True, shortened)


@pytest.mark.skipif(sys.platform != "win32", reason="Windows path limits")
def test_seed_image_read_through_short_path(tmp_path: Path, mocker: MockerFixture, no_seed_session: Session) -> None:
    wheel: Final[Path] = BUNDLE_FOLDER / BUNDLE_SUPPORT[no_seed_session.interpreter.version_release_str]["pip"]
    image: Final[Path] = tmp_path / "image" / "CopyPipInstall" / wheel.stem
    # an upper case name stands in for the short one, Windows opens the same directory through either
    mocker.patch(
        "virtualenv.seed.embed.via_app_data.pip_install.base.PipInstall._short_path_if_needed",
        autospec=True,
        side_effect=lambda _zip_ref, folder: folder.with_name(folder.name.upper()),
    )
    synced: Final[SpyType] = mocker.spy(CopyPipInstall, "_sync")
    built: Final[CopyPipInstall] = CopyPipInstall(wheel, no_seed_session.creator, image)
    built.build_image()
    built.install(no_seed_session.interpreter.version_info)
    read_after_build: Final[set[str]] = {str(call.args[1].parent) for call in synced.call_args_list}
    synced.reset_mock()
    reused: Final[CopyPipInstall] = CopyPipInstall(wheel, no_seed_session.creator, image)
    found: Final[bool] = reused.has_image()
    reused.install(no_seed_session.interpreter.version_info)
    read_on_reuse: Final[set[str]] = {str(call.args[1].parent) for call in synced.call_args_list}
    short: Final[str] = str(image.with_name(image.name.upper()))
    assert (read_after_build, found, read_on_reuse) == ({short}, True, {short})


def _read_windows_launcher(script: Path) -> bytes:
    with zipfile.ZipFile(script) as archive:
        return archive.read("__main__.py")


@pytest.mark.parametrize(
    "read_source",
    [
        pytest.param(
            Path.read_bytes, id="posix", marks=pytest.mark.skipif(sys.platform == "win32", reason="POSIX script")
        ),
        pytest.param(
            _read_windows_launcher,
            id="windows",
            marks=pytest.mark.skipif(sys.platform != "win32", reason="Windows launcher is an executable"),
        ),
    ],
)
def test_seed_entry_points_preserve_case_and_last_duplicate(
    tmp_path: Path, read_source: Callable[[Path], bytes]
) -> None:
    session = cli_run([str(tmp_path / "env"), "--no-seed"])
    image = tmp_path / "image"
    metadata = image / "example-1.dist-info"
    metadata.mkdir(parents=True)
    (metadata / "entry_points.txt").write_text(
        "[console_scripts]\nMyTool = old:main\nMyTool = example:main\n", encoding="utf-8"
    )
    CopyPipInstall(tmp_path / "example-1-py3-none-any.whl", session.creator, image).install(
        session.interpreter.version_info
    )
    assert b"from example import main" in read_source(session.creator.script("MyTool"))


@pytest.mark.parametrize(
    "script_name",
    [
        pytest.param("python3-config", id="interpreter-like"),
        pytest.param("2to3", id="leading-digits"),
        pytest.param("3to2", id="trailing-digits-after-text"),
    ],
)
def test_seed_entry_points_keep_names_that_are_not_version_suffixes(
    no_seed_session: Session, install_console_scripts: Callable[[str], None], script_name: str
) -> None:
    install_console_scripts(f"{script_name} = example:main\n")
    assert no_seed_session.creator.script(script_name).exists(), (
        f"{script_name} was not installed; got {sorted(i.name for i in no_seed_session.creator.script_dir.iterdir())}"
    )


def test_seed_entry_points_do_not_overwrite_the_interpreter(
    no_seed_session: Session, install_console_scripts: Callable[[str], None]
) -> None:
    original: Final[bytes] = no_seed_session.creator.exe.read_bytes()
    install_console_scripts("python3-config = example:main\n")
    assert no_seed_session.creator.exe.read_bytes() == original, "a generated script replaced the interpreter"


def test_seed_entry_points_still_fold_version_suffixed_names(
    no_seed_session: Session, install_console_scripts: Callable[[str], None]
) -> None:
    major, minor = no_seed_session.interpreter.version_info[:2]
    install_console_scripts(f"pip{major}.{minor} = example:main\npip{major} = example:main\n")
    # a single base regenerates these, an extra one per declared name would add names like `pip33`
    expected: Final[tuple[str, str, str, str]] = ("pip", f"pip{major}", f"pip{major}.{minor}", f"pip-{major}.{minor}")
    assert [name for name in expected if not no_seed_session.creator.script(name).exists()] == []


@pytest.mark.skipif(not fs_supports_symlink(), reason="requires symlinks")
@pytest.mark.parametrize(
    "script_name",
    [
        pytest.param(
            "{link}",
            id="absolute",
            marks=pytest.mark.skipif(os.name == "nt", reason="drive colon is an entry delimiter"),
        ),
        pytest.param("../../outside", id="parent"),
        pytest.param("sub/outside", id="linked-folder"),
        pytest.param(
            "{root_link}",
            id="windows-root",
            marks=pytest.mark.skipif(os.name != "nt", reason="requires a Windows drive-rooted path"),
        ),
    ],
)
def test_seed_entry_points_leave_outside_symlink_on_invalid_name(
    tmp_path: Path,
    no_seed_session: Session,
    install_console_scripts: Callable[[str], None],
    script_name: str,
) -> None:
    target: Final[Path] = tmp_path / "target"
    target.write_text("keep", encoding="utf-8")
    link: Final[Path] = tmp_path / ("outside.exe" if os.name == "nt" else "outside")
    link.symlink_to(target)
    (no_seed_session.creator.script_dir / "sub").symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(RuntimeError, match="invalid seed wheel script"):
        install_console_scripts(
            f"{script_name.format(link=link, root_link=os.path.splitdrive(str(link.with_suffix('')))[1])} = example:main\n"
        )
    assert (link.is_symlink(), target.read_text(encoding="utf-8")) == (True, "keep")


@pytest.mark.skipif(not fs_supports_symlink(), reason="requires symlinks")
def test_seed_entry_points_replace_in_directory_symlink(
    tmp_path: Path, no_seed_session: Session, install_console_scripts: Callable[[str], None]
) -> None:
    target: Final[Path] = tmp_path / "target"
    target.write_text("keep", encoding="utf-8")
    link: Final[Path] = no_seed_session.creator.script("example")
    link.symlink_to(target)
    install_console_scripts("example = example:main\n")
    assert (link.is_symlink(), link.is_file(), target.read_text(encoding="utf-8")) == (False, True, "keep")


@pytest.fixture
def no_seed_session(tmp_path: Path) -> Session:
    return cli_run([str(tmp_path / "env"), "--no-seed"])


@pytest.fixture
def install_console_scripts(tmp_path: Path, no_seed_session: Session) -> Callable[[str], None]:
    def install(entries: str) -> None:
        image: Final[Path] = tmp_path / "image"
        metadata: Final[Path] = image / "example-1.dist-info"
        metadata.mkdir(parents=True)
        (metadata / "entry_points.txt").write_text(f"[console_scripts]\n{entries}", encoding="utf-8")
        CopyPipInstall(tmp_path / "example-1-py3-none-any.whl", no_seed_session.creator, image).install(
            no_seed_session.interpreter.version_info
        )

    return install


@pytest.mark.skipif(not fs_supports_symlink(), reason="requires symlinks")
def test_symlink_seed_compiles_with_empty_local_module(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "compileall.py").touch()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PYTHONHOME", sys.base_prefix)
    session: Final[Session] = cli_run([
        str(tmp_path / "env"),
        "--symlink-app-data",
        "--pip",
        "embed",
        "--app-data",
        str(tmp_path / "cache"),
        "--no-periodic-update",
    ])
    assert list((session.creator.purelib / "pip" / "__pycache__").glob("__init__*.pyc"))


@pytest.mark.skipif(not fs_supports_symlink(), reason="requires symlinks")
@pytest.mark.skipif(sys.implementation.name != "cpython", reason="only CPython rejects an invalid PYTHONHOME")
def test_symlink_seed_uses_explicit_environment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env = os.environ.copy()
    env.pop("PYTHONHOME", None)
    monkeypatch.setenv("PYTHONHOME", str(tmp_path / "missing-home"))
    session = cli_run(
        [
            str(tmp_path / "env"),
            "--creator",
            "builtin",
            "--symlink-app-data",
            "--pip",
            "embed",
            "--setuptools",
            "none",
            "--app-data",
            str(tmp_path / "cache"),
            "--no-download",
            "--no-periodic-update",
            "--activators=",
        ],
        env=env,
    )
    assert list((session.creator.purelib / "pip" / "__pycache__").glob("__init__*.pyc"))


@pytest.mark.skipif(not fs_supports_symlink(), reason="requires symlinks")
def test_symlink_seed_reports_compilation_failure(tmp_path: Path, mocker: MockerFixture) -> None:
    mocker.patch(
        "virtualenv.seed.embed.via_app_data.pip_install.symlink.run_cmd",
        autospec=True,
        return_value=(7, "", "compilation failed"),
    )
    with pytest.raises(RuntimeError, match="compilation failed"):
        cli_run([
            str(tmp_path / "env"),
            "--symlink-app-data",
            "--pip",
            "embed",
            "--app-data",
            str(tmp_path / "cache"),
            "--no-periodic-update",
        ])


@pytest.mark.skipif(os.name != "posix", reason="POSIX shell launchers")
@pytest.mark.parametrize(
    ("name", "via_shell"),
    [
        pytest.param("plain", False, id="plain"),
        pytest.param("two words", True, id="space"),
        pytest.param("env\tname", True, id="tab"),
        pytest.param("env\vname", True, id="vertical-tab"),
        pytest.param("env\fname", True, id="form-feed"),
        pytest.param("rock'n'roll", True, id="apostrophe"),
        pytest.param("back\\slash", True, id="backslash"),
    ],
)
def test_pip_launcher_record_matches_contents(tmp_path: Path, name: str, via_shell: bool) -> None:
    session: Final[Session] = cli_run([
        str(tmp_path / name),
        "--seeder",
        "pip",
        "--pip",
        "embed",
        "--no-periodic-update",
    ])
    record: Final[Path] = next(session.creator.purelib.glob("pip-*.dist-info/RECORD"))
    with record.open(encoding="utf-8", newline="") as stream:
        row: Final[list[str]] = next(row for row in csv.reader(stream) if row[0].endswith("/bin/pip"))
    content: Final[bytes] = (session.creator.script_dir / "pip").read_bytes()
    assert content.startswith(b"#!/bin/sh\n") is via_shell
    assert row[1:] == [
        f"sha256={urlsafe_b64encode(hashlib.sha256(content).digest()).rstrip(b'=').decode('ascii')}",
        str(len(content)),
    ]


@pytest.mark.skipif(os.name != "posix" or sys.platform == "darwin", reason="requires raw POSIX filename bytes")
def test_shell_launcher_runs_interpreter_with_non_utf8_path(tmp_path: Path) -> None:
    interpreter: Final[Path] = Path(os.fsdecode(os.fsencode(tmp_path) + b"/\xff/python"))
    interpreter.parent.mkdir()
    interpreter.write_bytes(b"#!/bin/sh\nprintf '%s\\n' \"$0\"\n")
    interpreter.chmod(0o755)
    header: Final[bytes] = shell_shebang(str(interpreter))
    launcher: Final[Path] = tmp_path / "launcher"
    launcher.write_bytes(header)
    launcher.chmod(0o755)
    result: Final[CompletedProcess[bytes]] = run([launcher], capture_output=True, check=True)
    assert (header.isascii(), result.stdout) == (True, os.fsencode(interpreter) + b"\n")
    compile(header + b"pass\n", str(launcher), "exec")


@pytest.mark.skipif(os.name != "posix", reason="POSIX shell launchers")
@pytest.mark.parametrize(
    "name",
    [
        pytest.param("line\nunused_variable", id="interpreter-header"),
        pytest.param(f"{'x' * 120}\nx\nunused_variable", id="long-shell-header"),
        pytest.param("two words\nx\nunused_variable", id="shell-header"),
    ],
)
def test_pip_launcher_keeps_line_feed_path_in_header(tmp_path: Path, name: str) -> None:
    session: Final[Session] = cli_run([
        str(tmp_path / name),
        "--seeder",
        "pip",
        "--pip",
        "embed",
        "--no-periodic-update",
    ])
    result: Final[CompletedProcess[str]] = run(
        [str(session.creator.script_dir / "pip"), "--version"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
        check=False,
    )
    assert (result.returncode, result.stdout.startswith("pip ")) == (0, True)


def test_seed_worker_error_reaches_caller(tmp_path: Path, mocker: MockerFixture) -> None:
    mocker.patch(
        "virtualenv.seed.embed.via_app_data.via_app_data.get_wheel", autospec=True, side_effect=SystemError("lookup")
    )
    mocker.patch.object(logging.Logger, "exception", autospec=True, side_effect=TypeError("logging"))

    with pytest.raises(TypeError, match="logging"):
        cli_run([str(tmp_path / "env"), "--no-periodic-update", "--no-setuptools"])
