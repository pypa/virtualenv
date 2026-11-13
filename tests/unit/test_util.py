from __future__ import annotations

import concurrent.futures
import ctypes
import os
import shutil
import subprocess
import sys
import traceback
import zipfile
from errno import EACCES
from operator import attrgetter
from stat import S_IEXEC, S_IREAD, S_IRGRP, S_IRWXU, S_IWUSR
from typing import TYPE_CHECKING, Final

import pytest

from virtualenv import __version__
from virtualenv.app_data import AppDataDiskFolder, TempAppData, make_app_data
from virtualenv.info import fs_supports_symlink
from virtualenv.util import zipapp
from virtualenv.util.lock import ReentrantFileLock
from virtualenv.util.path import copy, ensure_within, safe_delete, symlink, write_file
from virtualenv.util.subprocess import run_cmd

if os.name == "nt":
    from ctypes import wintypes


if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from pytest_mock import MockerFixture


_DEFAULT_APP_DATA_ENVS: Final[list[pytest.ParameterSet]] = [
    pytest.param({}, id="unset"),
    pytest.param({"VIRTUALENV_OVERRIDE_APP_DATA": ""}, id="empty-override"),
    pytest.param({"VIRTUALENV_OVERRIDE_APP_DATA": " "}, id="blank-override"),
]


def _make_app_data_with_zero_umask(env: dict[str, str]) -> TempAppData | AppDataDiskFolder:
    previous: Final = os.umask(0)
    try:
        return make_app_data(None, read_only=False, env=env)
    finally:
        os.umask(previous)


@pytest.mark.skipif(os.name != "posix", reason="POSIX directory permission bits")
@pytest.mark.parametrize("env", _DEFAULT_APP_DATA_ENVS)
def test_app_data_default_permissions_new(app_data_default: Path, env: dict[str, str]) -> None:
    data: Final = _make_app_data_with_zero_umask(env)
    assert (str(data), app_data_default.stat().st_mode & 0o777) == (str(app_data_default), 0o700)


@pytest.mark.skipif(os.name != "posix", reason="POSIX directory permission bits")
@pytest.mark.parametrize("env", _DEFAULT_APP_DATA_ENVS)
def test_app_data_default_permissions_existing(app_data_default: Path, env: dict[str, str]) -> None:
    app_data_default.mkdir()
    app_data_default.chmod(0o777)
    data: Final = _make_app_data_with_zero_umask(env)
    assert (str(data), app_data_default.stat().st_mode & 0o777) == (str(app_data_default), 0o755)


@pytest.mark.skipif(os.name != "posix", reason="POSIX directory permission bits")
def test_app_data_argument_permissions(tmp_path: Path) -> None:
    tmp_path.chmod(0o775)
    data: Final = make_app_data(str(tmp_path), read_only=False, env={})
    assert (str(data), tmp_path.stat().st_mode & 0o777) == (str(tmp_path), 0o775)


@pytest.mark.skipif(os.name != "posix", reason="POSIX directory permission bits")
def test_app_data_environment_permissions(tmp_path: Path) -> None:
    tmp_path.chmod(0o775)
    data: Final = make_app_data(None, read_only=False, env={"VIRTUALENV_OVERRIDE_APP_DATA": str(tmp_path)})
    assert (str(data), tmp_path.stat().st_mode & 0o777) == (str(tmp_path), 0o775)


def test_app_data_read_only_does_not_create(app_data_default: Path) -> None:
    with pytest.raises(RuntimeError, match="does not exist"):
        make_app_data(None, read_only=True, env={})
    assert not app_data_default.exists()


@pytest.mark.skipif(os.name != "posix", reason="POSIX directory permission bits")
def test_app_data_read_only_permissions(app_data_default: Path) -> None:
    app_data_default.mkdir()
    app_data_default.chmod(0o775)
    data: Final = make_app_data(None, read_only=True, env={})
    assert (str(data), app_data_default.stat().st_mode & 0o777) == (str(app_data_default), 0o775)


def test_app_data_default_writable(app_data_default: Path) -> None:
    data: Final = make_app_data(None, read_only=False, env={})
    target: Final = app_data_default / "entry"
    target.write_text("cached", encoding="utf-8")
    assert (str(data), target.read_text(encoding="utf-8"), data.transient) == (
        str(app_data_default),
        "cached",
        False,
    )


@pytest.mark.skipif(os.name != "posix", reason="POSIX directory permission bits")
def test_app_data_permission_failure_uses_temporary(app_data_default: Path, mocker: MockerFixture) -> None:
    app_data_default.mkdir()
    app_data_default.chmod(0o777)
    mocker.patch("virtualenv.app_data.factory.os.chmod", autospec=True, side_effect=PermissionError)
    data: Final = make_app_data(None, read_only=False, env={})
    try:
        assert isinstance(data, TempAppData)
        assert str(data) != str(app_data_default)
    finally:
        data.close()


@pytest.mark.parametrize("writable", [pytest.param(False, id="unwritable"), pytest.param(True, id="writable")])
def test_app_data_explicit_create_failure(tmp_path: Path, mocker: MockerFixture, writable: bool) -> None:
    mocker.patch("virtualenv.app_data.factory.os.makedirs", autospec=True, side_effect=PermissionError)
    mocker.patch("virtualenv.app_data.factory.os.access", autospec=True, return_value=writable)
    data: Final = make_app_data(str(tmp_path), read_only=False, env={})
    try:
        assert (data.transient, str(data) == str(tmp_path)) == (not writable, writable)
    finally:
        data.close()


@pytest.fixture
def app_data_default(tmp_path: Path, mocker: MockerFixture, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(tmp_path)  # a blank override resolved to the working directory, so keep that inside tmp_path
    folder: Final = tmp_path / "cache"
    mocker.patch("virtualenv.app_data.cache_migration.user_cache_dir", autospec=True, return_value=str(folder))
    mocker.patch("virtualenv.app_data.cache_migration.user_data_dir", autospec=True, return_value=str(tmp_path / "old"))
    return folder


@pytest.mark.skipif(os.name != "posix", reason="POSIX permission bits")
@pytest.mark.parametrize("layout", [pytest.param(("entry", ""), id="file"), pytest.param(("", "entry"), id="tree")])
@pytest.mark.parametrize(
    ("source_mode", "mask", "expected"),
    [
        pytest.param(0o666, 0o022, 0o644, id="normal"),
        pytest.param(0o666, 0o077, 0o600, id="private"),
        pytest.param(0o444, 0o022, 0o644, id="read-only-source"),
        pytest.param(0o600, 0o022, 0o644, id="private-source"),
        pytest.param(0o777, 0o022, 0o755, id="executable"),
        pytest.param(0o777, 0o077, 0o700, id="private-executable"),
        pytest.param(0o666, 0o000, 0o644, id="permissive-umask"),
        pytest.param(0o777, 0o000, 0o755, id="permissive-executable"),
        pytest.param(0o666, 0o002, 0o644, id="group-umask"),
        pytest.param(0o777, 0o002, 0o755, id="group-executable"),
    ],
)
def test_copy_uses_current_umask(
    tmp_path: Path, layout: tuple[str, str], source_mode: int, mask: int, expected: int
) -> None:
    source_rel, result_rel = layout
    source: Final = tmp_path / "source"
    source.mkdir()
    payload: Final = source / "entry"
    payload.write_bytes(b"copied bytes")
    payload.chmod(source_mode)
    destination: Final = tmp_path / "destination"
    previous: Final = os.umask(mask)
    try:
        copy(source / source_rel, destination)
    finally:
        os.umask(previous)
    result: Final = destination / result_rel
    assert (result.read_bytes(), result.stat().st_mode & 0o777) == (b"copied bytes", expected)


@pytest.mark.parametrize("layout", [pytest.param(("entry", ""), id="file"), pytest.param(("", "entry"), id="tree")])
def test_copy_replaces_contents(tmp_path: Path, layout: tuple[str, str]) -> None:
    source_rel, result_rel = layout
    source: Final = tmp_path / "source"
    source.mkdir()
    (source / "entry").write_bytes(b"new")
    destination: Final = tmp_path / "destination"
    destination.write_bytes(b"old")
    copy(source / source_rel, destination)
    assert (destination / result_rel).read_bytes() == b"new"


def test_copy_replaces_read_only_file(tmp_path: Path) -> None:
    (source := tmp_path / "source").write_bytes(b"new")
    (destination := tmp_path / "destination").write_bytes(b"old")
    destination.chmod(S_IREAD)
    copy(source, destination)
    assert destination.read_bytes() == b"new"


@pytest.mark.skipif(not fs_supports_symlink(), reason="symlinks are unavailable")
def test_copy_keeps_symlinked_directories(tmp_path: Path) -> None:
    source: Final = tmp_path / "source"
    source.mkdir()
    target: Final = source / "target"
    target.mkdir()
    (target / "inside.txt").write_text("content", encoding="utf-8")
    (source / "link_to_file").symlink_to(target / "inside.txt")
    (source / "link_to_dir").symlink_to(target, target_is_directory=True)

    destination: Final = tmp_path / "destination"
    copy(source, destination)

    assert (
        (destination / "link_to_file").read_text(encoding="utf-8"),
        (destination / "link_to_dir" / "inside.txt").read_text(encoding="utf-8"),
    ) == ("content", "content")


@pytest.mark.skipif(not fs_supports_symlink(), reason="symlinks are unavailable")
@pytest.mark.parametrize("target", [pytest.param(".", id="itself"), pytest.param("..", id="above-source")])
def test_copy_does_not_expand_a_symlinked_directory_pointing_at_a_parent(tmp_path: Path, target: str) -> None:
    source: Final = tmp_path / "source"
    source.mkdir()
    (source / "entry.txt").write_text("content", encoding="utf-8")
    (source / "loop").symlink_to(target, target_is_directory=True)

    destination: Final = tmp_path / "destination"
    copy(source, destination)

    assert sorted(i.name for i in destination.iterdir()) == ["entry.txt"]


@pytest.mark.skipif(sys.platform != "linux", reason="minimal Linux builds can omit ctypes")
def test_command_line_import_without_ctypes() -> None:
    result: Final = run_cmd([
        sys.executable,
        "-c",
        (
            "import runpy, sys; sys.modules['ctypes'] = None; sys.argv = ['virtualenv', '--version']; "
            "runpy.run_module('virtualenv', run_name='__main__')"
        ),
    ])
    assert (result[0], __version__ in result[1], result[2]) == (0, True, "")


@pytest.mark.skipif(os.name != "nt", reason="Windows file attributes")
@pytest.mark.parametrize(
    ("operation", "failure_return"),
    [
        pytest.param("CreateFileW", lambda: wintypes.HANDLE(-1).value, id="open"),
        pytest.param("GetFileInformationByHandleEx", lambda: 0, id="read"),
        pytest.param("SetFileInformationByHandle", lambda: 0, id="write"),
    ],
)
def test_safe_delete_reports_attribute_errors(
    tmp_path: Path, mocker: MockerFixture, operation: str, failure_return: Callable[[], int]
) -> None:
    folder: Final = tmp_path / "folder"
    folder.mkdir()
    source: Final = folder / "read-only"
    source.touch()
    source.chmod(S_IREAD)
    kernel: Final = ctypes.WinDLL("kernel32", use_last_error=True)
    mocker.patch.object(kernel, operation, autospec=True, return_value=failure_return())
    mocker.patch("ctypes.WinDLL", autospec=True, return_value=kernel)
    mocker.patch("ctypes.get_last_error", autospec=True, return_value=5)
    with pytest.raises(PermissionError, match="WinError 5"):
        safe_delete(folder)
    assert source.stat().st_mode & S_IWUSR == 0
    source.chmod(S_IREAD | S_IWUSR)


@pytest.mark.skipif(not fs_supports_symlink(), reason="symlinks are unavailable")
def test_safe_delete_does_not_chmod_link_target(tmp_path: Path, mocker: MockerFixture) -> None:
    source: Final = tmp_path / "read-only"
    source.write_text("unchanged", encoding="utf-8")
    source.chmod(S_IREAD)
    mode: Final = source.stat().st_mode
    folder: Final = tmp_path / "folder"
    folder.mkdir()
    (folder / "link").symlink_to(source)
    unlink: Final = mocker.patch("os.unlink", autospec=True, side_effect=PermissionError(EACCES, "entry is busy"))
    try:
        with pytest.raises(PermissionError, match="entry is busy"):
            safe_delete(folder)
    finally:
        mocker.stop(unlink)
    assert source.stat().st_mode == mode


def test_write_file_creates_missing_file(tmp_path: Path) -> None:
    path: Final = tmp_path / "generated"
    write_file(path, b"generated")
    assert path.read_bytes() == b"generated"


def test_write_file_replaces_content(tmp_path: Path) -> None:
    path: Final = tmp_path / "generated"
    path.write_bytes(b"previous")
    write_file(path, b"generated")
    assert path.read_bytes() == b"generated"


def test_write_file_replaces_read_only_file(tmp_path: Path) -> None:
    (path := tmp_path / "generated").write_bytes(b"previous")
    path.chmod(S_IREAD)
    write_file(path, b"generated")
    assert path.read_bytes() == b"generated"


@pytest.mark.skipif(os.name == "nt" or os.geteuid() == 0, reason="POSIX deletion permissions that root bypasses")
def test_write_file_reports_read_only_directory(tmp_path: Path) -> None:
    (folder := tmp_path / "locked").mkdir()
    (folder / "generated").write_bytes(b"previous")
    folder.chmod(S_IREAD | S_IEXEC)
    try:
        with pytest.raises(PermissionError):
            write_file(folder / "generated", b"generated")
    finally:
        folder.chmod(S_IRWXU)


def test_environment_directories_create_nested_path(tmp_path: Path) -> None:
    folder: Final = tmp_path / "env" / "lib" / "python"
    ensure_within(tmp_path / "env", folder)
    assert folder.is_dir()


def test_environment_directories_keep_existing_nested_path(tmp_path: Path) -> None:
    folder: Final = tmp_path / "env" / "lib" / "python"
    folder.mkdir(parents=True)
    ensure_within(tmp_path / "env", folder)
    assert folder.is_dir()


def test_environment_directories_reject_regular_file(tmp_path: Path) -> None:
    folder: Final = tmp_path / "file"
    folder.touch()
    with pytest.raises(NotADirectoryError, match="not a real directory"):
        ensure_within(tmp_path, folder)


def test_environment_directories_reject_parent_components(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="must remain inside"):
        ensure_within(tmp_path, tmp_path / ".." / "folder")


@pytest.mark.skipif(not fs_supports_symlink(), reason="symlinks are unavailable")
def test_environment_directories_remove_links_to_missing_target(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    target: Final = tmp_path / "stored"
    link: Final = tmp_path / "link"
    link.symlink_to(target, target_is_directory=True)
    ensure_within(tmp_path, link / "nested")
    assert (
        link.is_symlink(),
        link.exists(),
        target.exists(),
        f"replace environment directory link {link}" in caplog.text,
    ) == (False, True, False, True)


@pytest.mark.skipif(not fs_supports_symlink(), reason="symlinks are unavailable")
def test_environment_directories_remove_links_to_existing_target(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    target: Final = tmp_path / "stored"
    target.mkdir()
    link: Final = tmp_path / "link"
    link.symlink_to(target, target_is_directory=True)
    ensure_within(tmp_path, link / "nested")
    assert (
        link.is_symlink(),
        link.exists(),
        target.exists(),
        f"replace environment directory link {link}" in caplog.text,
    ) == (False, True, True, True)


@pytest.mark.skipif(os.name != "nt", reason="Windows junctions")
def test_environment_directories_report_replaced_junction(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    target: Final = tmp_path / "stored"
    target.mkdir()
    link: Final = tmp_path / "link"
    subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(target)], check=True, capture_output=True)
    ensure_within(tmp_path, link)
    assert (link.resolve(), f"replace environment directory junction {link}" in caplog.text) == (link, True)


def test_run_fail(tmp_path) -> None:
    code, out, err = run_cmd([str(tmp_path)])
    assert err
    assert not out
    assert code


def test_safe_delete_removes_read_only_files(tmp_path: Path) -> None:
    target = tmp_path / "target"
    nested = target / "sub"
    nested.mkdir(parents=True)
    # the wheel image marks its files read-only via set_tree, which on Windows blocks os.unlink
    marked = nested / "wheel.py"
    marked.write_text("cached", encoding="utf-8")
    marked.chmod(S_IREAD)

    safe_delete(target)

    assert not target.exists()


def test_safe_delete_missing_path_is_noop(tmp_path: Path) -> None:
    safe_delete(tmp_path / "does-not-exist")  # --reset-app-data before anything was cached


@pytest.mark.skipif(sys.platform != "win32", reason="only Windows blocks deleting an open file")
def test_safe_delete_surfaces_undeletable_entries(tmp_path: Path) -> None:
    target = tmp_path / "target"
    target.mkdir()
    busy = target / "busy.txt"
    busy.write_text("x", encoding="utf-8")

    with busy.open(encoding="utf-8"), pytest.raises(OSError, match="busy"):
        safe_delete(target)


@pytest.mark.skipif(sys.platform == "win32", reason="Windows deletion ignores directory permissions")
@pytest.mark.skipif(hasattr(os, "geteuid") and os.geteuid() == 0, reason="root bypasses the permission bits")
def test_safe_delete_raises_the_original_error_not_a_retry_failure(tmp_path: Path) -> None:
    target = tmp_path / "target"
    blocked = target / "sub"
    blocked.mkdir(parents=True)
    (blocked / "wheel.py").write_text("cached", encoding="utf-8")
    blocked.chmod(0o000)  # rmtree reports this one through os.open, which takes more than a path

    try:
        with pytest.raises(PermissionError):
            safe_delete(target)
    finally:
        blocked.chmod(S_IRWXU)


@pytest.mark.skipif(sys.platform == "win32", reason="Windows deletion ignores directory permissions")
@pytest.mark.skipif(hasattr(os, "geteuid") and os.geteuid() == 0, reason="root bypasses the permission bits")
def test_safe_delete_preserves_file_mode_when_parent_denies_deletion(tmp_path: Path) -> None:
    target = tmp_path / "target"
    target.mkdir()
    blocked = target / "wheel.py"
    blocked.write_text("cached", encoding="utf-8")
    blocked.chmod(S_IREAD | S_IRGRP)
    target.chmod(S_IREAD | S_IEXEC)  # the unlink fails, so the mode the handler left behind stays observable

    try:
        with pytest.raises(PermissionError):
            safe_delete(target)
        assert blocked.stat().st_mode & 0o777 == S_IREAD | S_IRGRP
    finally:
        target.chmod(S_IRWXU)


@pytest.mark.skipif(not fs_supports_symlink(), reason="symlink is not supported")
@pytest.mark.parametrize(
    ("layout", "directory"),
    [
        pytest.param(("file.txt", ""), False, id="file"),
        pytest.param(("", "file.txt"), True, id="directory"),
    ],
)
@pytest.mark.parametrize(
    "link_to",
    [pytest.param("outside", id="missing-target"), pytest.param("destination", id="self-loop")],
)
def test_copy_replaces_dangling_symlink(tmp_path: Path, layout: tuple[str, str], directory: bool, link_to: str) -> None:
    source_rel, result_rel = layout
    source: Final[Path] = tmp_path / "source"
    source.mkdir()
    (source / "file.txt").write_text("new", encoding="utf-8")
    destination: Final[Path] = tmp_path / "destination"
    outside: Final[Path] = tmp_path / "outside"
    destination.symlink_to(tmp_path / link_to, target_is_directory=directory)

    copy(source / source_rel, destination)

    assert (
        destination.is_symlink(),
        (destination / result_rel).read_text(encoding="utf-8"),
        destination.resolve(),
        outside.exists(),
    ) == (False, "new", destination, False)


@pytest.mark.skipif(not fs_supports_symlink(), reason="symlink is not supported")
@pytest.mark.parametrize(
    ("layout", "directory"),
    [
        pytest.param(("file.txt", ""), False, id="file"),
        pytest.param(("", "file.txt"), True, id="directory"),
    ],
)
@pytest.mark.parametrize(
    "link_to",
    [pytest.param("outside", id="missing-target"), pytest.param("destination", id="self-loop")],
)
def test_symlink_replaces_dangling_symlink(
    tmp_path: Path, layout: tuple[str, str], directory: bool, link_to: str
) -> None:
    source_rel, result_rel = layout
    source: Final[Path] = tmp_path / "source"
    source.mkdir()
    (source / "file.txt").write_text("new", encoding="utf-8")
    destination: Final[Path] = tmp_path / "destination"
    outside: Final[Path] = tmp_path / "outside"
    destination.symlink_to(tmp_path / link_to, target_is_directory=directory)

    symlink(source / source_rel, destination)

    assert (
        destination.is_symlink(),
        (destination / result_rel).read_text(encoding="utf-8"),
        destination.resolve(),
        outside.exists(),
    ) == (True, "new", (source / source_rel).resolve(), False)


def test_reentrant_file_lock_is_thread_safe(tmp_path) -> None:
    lock = ReentrantFileLock(tmp_path)
    target_file = tmp_path / "target"
    target_file.touch()

    def recreate_target_file() -> None:
        with lock.lock_for_key("target"):
            target_file.unlink()
            target_file.touch()

    with concurrent.futures.ThreadPoolExecutor() as executor:
        tasks = [executor.submit(recreate_target_file) for _ in range(4)]
        concurrent.futures.wait(tasks)
        for task in tasks:
            try:
                task.result()
            # every failed task's traceback is collected, one bad task must not stop the loop
            except Exception:  # ruff:ignore[blind-except, try-except-in-loop]
                pytest.fail(traceback.format_exc())


def test_default_app_data_dir_override_env_var(tmp_path: Path) -> None:
    custom = str(tmp_path / "custom")
    env = {"VIRTUALENV_OVERRIDE_APP_DATA": custom}
    assert str(make_app_data(None, read_only=False, env=env)) == custom


def test_default_app_data_dir_no_override_returns_cache_dir(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("VIRTUALENV_OVERRIDE_APP_DATA", raising=False)
    result = str(make_app_data(None, read_only=False, env=os.environ))
    assert result


def test_cache_dir_migration_migrate_old_to_new(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    old_dir = str(tmp_path / "old-data")
    new_dir = str(tmp_path / "new-cache")
    os.makedirs(old_dir)
    (tmp_path / "old-data" / "test.txt").write_text("hello", encoding="utf-8")

    monkeypatch.setattr("virtualenv.app_data.cache_migration.user_cache_dir", lambda **_kw: new_dir)
    monkeypatch.setattr("virtualenv.app_data.cache_migration.user_data_dir", lambda **_kw: old_dir)

    result = str(make_app_data(None, read_only=False, env={}))
    assert result == new_dir
    assert os.path.isdir(new_dir)
    assert not os.path.isdir(old_dir)
    assert (tmp_path / "new-cache" / "test.txt").read_text(encoding="utf-8") == "hello"


def test_cache_dir_migration_no_migration_when_old_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    old_dir = str(tmp_path / "old-data")
    new_dir = str(tmp_path / "new-cache")

    monkeypatch.setattr("virtualenv.app_data.cache_migration.user_cache_dir", lambda **_kw: new_dir)
    monkeypatch.setattr("virtualenv.app_data.cache_migration.user_data_dir", lambda **_kw: old_dir)

    result = str(make_app_data(None, read_only=False, env={}))
    assert result == new_dir
    assert not os.path.isdir(old_dir)


def test_cache_dir_migration_no_migration_when_new_exists(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    old_dir = str(tmp_path / "old-data")
    new_dir = str(tmp_path / "new-cache")
    os.makedirs(old_dir)
    os.makedirs(new_dir)
    (tmp_path / "old-data" / "old.txt").write_text("old", encoding="utf-8")

    monkeypatch.setattr("virtualenv.app_data.cache_migration.user_cache_dir", lambda **_kw: new_dir)
    monkeypatch.setattr("virtualenv.app_data.cache_migration.user_data_dir", lambda **_kw: old_dir)

    result = str(make_app_data(None, read_only=False, env={}))
    assert result == new_dir
    assert os.path.isdir(old_dir)


def test_cache_dir_migration_same_dir_returns_immediately(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    same_dir = str(tmp_path / "same")
    monkeypatch.setattr("virtualenv.app_data.cache_migration.user_cache_dir", lambda **_kw: same_dir)
    monkeypatch.setattr("virtualenv.app_data.cache_migration.user_data_dir", lambda **_kw: same_dir)

    result = str(make_app_data(None, read_only=False, env={}))
    assert result == same_dir


def test_cache_dir_migration_fallback_on_migration_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    old_dir = str(tmp_path / "old-data")
    new_dir = str(tmp_path / "new-cache")
    os.makedirs(old_dir)

    monkeypatch.setattr("virtualenv.app_data.cache_migration.user_cache_dir", lambda **_kw: new_dir)
    monkeypatch.setattr("virtualenv.app_data.cache_migration.user_data_dir", lambda **_kw: old_dir)

    def broken_move(_src: str, _dst: str) -> None:
        msg = "permission denied"
        raise OSError(msg)

    monkeypatch.setattr("virtualenv.app_data.cache_migration.shutil.move", broken_move)

    result = str(make_app_data(None, read_only=False, env={}))
    assert result == old_dir


@pytest.mark.parametrize("symlink_flag", [True, False])
def test_cache_dir_migration_symlink_app_data_survives_migration(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    # the flag is parametrized to run the case twice, the body does not read it
    symlink_flag: bool,  # ruff:ignore[unused-function-argument]
) -> None:
    old_dir = str(tmp_path / "old-data")
    new_dir = str(tmp_path / "new-cache")
    os.makedirs(old_dir)
    wheel_img = tmp_path / "old-data" / "wheel" / "3.12" / "image" / "pip"
    wheel_img.mkdir(parents=True)
    (wheel_img / "pip.dist-info").mkdir()
    (wheel_img / "pip.dist-info" / "METADATA").write_text("Name: pip", encoding="utf-8")

    venv_dir = tmp_path / "my-venv" / "lib" / "site-packages"
    venv_dir.mkdir(parents=True)
    try:
        os.symlink(str(wheel_img / "pip.dist-info"), str(venv_dir / "pip.dist-info"))
    except OSError:
        pytest.skip("symlinks not supported on this filesystem")

    monkeypatch.setattr("virtualenv.app_data.cache_migration.user_cache_dir", lambda **_kw: new_dir)
    monkeypatch.setattr("virtualenv.app_data.cache_migration.user_data_dir", lambda **_kw: old_dir)

    result = str(make_app_data(None, read_only=False, env={}))
    assert result == new_dir
    assert (tmp_path / "new-cache" / "wheel" / "3.12" / "image" / "pip" / "pip.dist-info" / "METADATA").exists()


@pytest.mark.parametrize(
    ("new_dir_rel", "old_dir_value"),
    [
        pytest.param("data/Cache", str, id="nested-cache"),
        pytest.param("cache", str, id="sibling-cache"),
        pytest.param("cache", attrgetter("name"), id="relative-data-dir"),
    ],
)
def test_cache_dir_migrates_contents(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mocker: MockerFixture,
    new_dir_rel: str,
    old_dir_value: Callable[[Path], str],
) -> None:
    monkeypatch.chdir(tmp_path)
    old_dir: Final = tmp_path / "data"
    old_dir.mkdir()
    (old_dir / "test.txt").write_text("hello", encoding="utf-8")
    new_dir: Final = tmp_path / new_dir_rel
    mocker.patch("virtualenv.app_data.cache_migration.user_cache_dir", autospec=True, return_value=str(new_dir))
    mocker.patch(
        "virtualenv.app_data.cache_migration.user_data_dir", autospec=True, return_value=old_dir_value(old_dir)
    )

    assert (str(make_app_data(None, read_only=False, env={})), (new_dir / "test.txt").read_text(encoding="utf-8")) == (
        str(new_dir),
        "hello",
    )


def test_cache_dir_nested_migration_keeps_parent(nested_cache_dirs: tuple[Path, Path]) -> None:
    make_app_data(None, read_only=False, env={})

    assert [entry.name for entry in nested_cache_dirs[0].iterdir()] == ["Cache"]


@pytest.mark.parametrize(
    ("rollback_error", "cleanup_error", "retry_index"),
    [
        pytest.param(None, None, 1, id="rollback-succeeds"),
        pytest.param(OSError("permission denied"), None, 0, id="rollback-fails"),
        pytest.param(None, OSError("permission denied"), 0, id="cleanup-fails"),
    ],
)
def test_cache_dir_nested_migration_failure_selection(
    nested_cache_dirs: tuple[Path, Path],
    mocker: MockerFixture,
    rollback_error: OSError | None,
    cleanup_error: OSError | None,
    retry_index: int,
) -> None:
    old_dir: Final = nested_cache_dirs[0]
    mocker.patch(
        "virtualenv.app_data.cache_migration.shutil.move",
        autospec=True,
        wraps=shutil.move,
        side_effect=[
            mocker.DEFAULT,
            OSError("permission denied"),
            rollback_error or mocker.DEFAULT,
            mocker.DEFAULT,
            mocker.DEFAULT,
        ],
    )
    mocker.patch(
        "virtualenv.app_data.cache_migration.os.rmdir", autospec=True, wraps=os.rmdir, side_effect=cleanup_error
    )

    assert (
        str(make_app_data(None, read_only=False, env={})),
        str(make_app_data(None, read_only=False, env={})),
    ) == (str(old_dir), str(nested_cache_dirs[retry_index]))


def test_cache_dir_interrupted_migration_keeps_old_location(
    nested_cache_dirs: tuple[Path, Path], mocker: MockerFixture
) -> None:
    mocker.patch(
        "virtualenv.app_data.cache_migration.shutil.move",
        autospec=True,
        wraps=shutil.move,
        side_effect=[mocker.DEFAULT, KeyboardInterrupt()],
    )

    with pytest.raises(KeyboardInterrupt):
        make_app_data(None, read_only=False, env={})

    assert str(make_app_data(None, read_only=False, env={})) == str(nested_cache_dirs[0])


def test_cache_dir_existing_nested_cache_stays_selected(nested_cache_dirs: tuple[Path, Path]) -> None:
    new_dir: Final = nested_cache_dirs[1]
    new_dir.mkdir()

    assert str(make_app_data(None, read_only=False, env={})) == str(new_dir)


@pytest.fixture
def nested_cache_dirs(tmp_path: Path, mocker: MockerFixture) -> tuple[Path, Path]:
    old_dir: Final = tmp_path / "data"
    old_dir.mkdir()
    (old_dir / "one.txt").write_text("one", encoding="utf-8")
    (old_dir / "two.txt").write_text("two", encoding="utf-8")
    new_dir: Final = old_dir / "Cache"
    mocker.patch("virtualenv.app_data.cache_migration.user_cache_dir", autospec=True, return_value=str(new_dir))
    mocker.patch("virtualenv.app_data.cache_migration.user_data_dir", autospec=True, return_value=str(old_dir))
    return old_dir, new_dir


@pytest.fixture
def fake_zipapp_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    fake_root = tmp_path / "virtualenv.pyz"
    with zipfile.ZipFile(str(fake_root), "w") as zip_file:
        zip_file.writestr("virtualenv/payload.txt", "hello zipapp")
    monkeypatch.setattr(zipapp, "ROOT", str(fake_root))
    return fake_root


def test_zipapp_read_returns_payload_from_entry_inside_root(fake_zipapp_root: Path) -> None:
    entry = fake_zipapp_root / "virtualenv" / "payload.txt"
    assert zipapp.read(entry) == "hello zipapp"


def test_zipapp_extract_uses_destination_name(fake_zipapp_root: Path, tmp_path: Path) -> None:
    dest = tmp_path / "renamed.txt"

    zipapp.extract(fake_zipapp_root / "virtualenv" / "payload.txt", dest)

    assert dest.read_text(encoding="utf-8") == "hello zipapp"


@pytest.mark.parametrize(
    "parts",
    [
        pytest.param(("virtualenv.pyz", "..", "escape.txt"), id="escapes-via-parent"),
        pytest.param(("other", "file.txt"), id="unrelated-absolute"),
    ],
)
def test_zipapp_read_rejects_path_outside_root(fake_zipapp_root: Path, parts: tuple[str, ...]) -> None:
    with pytest.raises(RuntimeError, match="should be within ROOT"):
        zipapp.read(fake_zipapp_root.parent.joinpath(*parts))


@pytest.mark.skipif(os.name != "posix", reason="POSIX directory permission bits")
@pytest.mark.parametrize(
    ("mode", "expected"),
    [pytest.param(0o2775, 0o2775, id="group-write"), pytest.param(0o2777, 0o2775, id="other-write")],
)
def test_app_data_setgid_keeps_group_write(app_data_default: Path, mode: int, expected: int) -> None:
    app_data_default.mkdir()
    app_data_default.chmod(mode)
    make_app_data(None, read_only=False, env={})
    assert app_data_default.stat().st_mode & 0o7777 == expected


@pytest.mark.skipif(os.name != "posix", reason="POSIX ownership")
def test_app_data_keeps_writable_non_owned_cache(app_data_default: Path, mocker: MockerFixture) -> None:
    app_data_default.mkdir()
    app_data_default.chmod(0o1777)
    mocker.patch(
        "virtualenv.app_data.factory.os.geteuid", autospec=True, return_value=app_data_default.stat().st_uid + 1
    )
    mocker.patch("virtualenv.app_data.factory.os.chmod", autospec=True, side_effect=PermissionError)
    data: Final = make_app_data(None, read_only=False, env={})
    assert (isinstance(data, AppDataDiskFolder), str(data), app_data_default.stat().st_mode & 0o7777) == (
        True,
        str(app_data_default),
        0o1777,
    )
