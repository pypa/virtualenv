from __future__ import annotations

import concurrent.futures
import ctypes
import os
import shutil
import subprocess
import sys
import threading
import traceback
import zipfile
from contextlib import ExitStack
from errno import EACCES, EXDEV
from pathlib import Path
from stat import S_IEXEC, S_IREAD, S_IRGRP, S_IRWXU, S_IWUSR, ST_UID
from typing import TYPE_CHECKING, Final

import pytest
from filelock import FileLock

from virtualenv import __version__
from virtualenv.app_data import AppDataDiskFolder, TempAppData, make_app_data
from virtualenv.app_data.cache_migration import cache_dir_with_migration
from virtualenv.info import fs_supports_symlink
from virtualenv.util import zipapp
from virtualenv.util.lock import ReentrantFileLock, Timeout
from virtualenv.util.path import (
    copy,
    ensure_within,
    get_short_path_name,
    owner_executable_mode,
    safe_delete,
    set_tree,
    symlink,
    write_file,
)
from virtualenv.util.subprocess import LogCmd, run_cmd

if os.name == "nt":
    from ctypes import wintypes


if TYPE_CHECKING:
    from collections.abc import Callable

    from pytest_mock import MockerFixture, MockType

    from virtualenv.app_data import AppData

_DEFAULT_APP_DATA_ENVS: Final[list[pytest.ParameterSet]] = [
    pytest.param({}, id="unset"),
    pytest.param({"VIRTUALENV_OVERRIDE_APP_DATA": ""}, id="empty-override"),
    pytest.param({"VIRTUALENV_OVERRIDE_APP_DATA": " "}, id="blank-override"),
]


@pytest.mark.skipif(sys.platform != "linux" or not hasattr(os, "getxattr"), reason="Linux default ACL detection")
def test_owner_executable_mode_reports_acl_read_error(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        owner_executable_mode(tmp_path / "missing", 0o600)


@pytest.mark.skipif(sys.platform == "linux" and hasattr(os, "getxattr"), reason="default ACL lookup available")
def test_owner_executable_mode_refuses_unverified_acl(tmp_path: Path) -> None:
    with pytest.raises(PermissionError, match=r"owner-executable.*--symlinks"):
        owner_executable_mode(tmp_path, 0o600)


def test_package_api_definition_modules() -> None:
    assert (make_app_data.__module__, LogCmd.__module__, run_cmd.__module__) == (
        "virtualenv.app_data",
        "virtualenv.util.subprocess",
        "virtualenv.util.subprocess",
    )


@pytest.mark.skipif(os.name != "posix", reason="POSIX directory permission bits")
@pytest.mark.parametrize("env", _DEFAULT_APP_DATA_ENVS)
def test_app_data_default_permissions_new(app_data_default: Path, env: dict[str, str]) -> None:
    data: Final[AppDataDiskFolder] = _make_app_data_with_zero_umask(env)
    assert (str(data), app_data_default.stat().st_mode & 0o777) == (str(app_data_default), 0o700)


def _make_app_data_with_zero_umask(env: dict[str, str]) -> TempAppData | AppDataDiskFolder:
    previous: Final[int] = os.umask(0)
    try:
        return make_app_data(None, read_only=False, env=env)
    finally:
        os.umask(previous)


@pytest.mark.skipif(os.name != "posix", reason="POSIX directory permission bits")
@pytest.mark.parametrize("mask", [pytest.param(0o002, id="shared-group"), pytest.param(0o000, id="world-writable")])
def test_app_data_default_missing_parent_private(tmp_path: Path, mocker: MockerFixture, mask: int) -> None:
    home: Final[Path] = tmp_path / "home"
    home.mkdir(mode=0o755)
    cache: Final[Path] = home / ".cache"
    folder: Final[Path] = cache / "virtualenv"
    mocker.patch("virtualenv.app_data.cache_migration.user_cache_dir", autospec=True, return_value=str(folder))
    mocker.patch("virtualenv.app_data.cache_migration.user_data_dir", autospec=True, return_value=str(home / "old"))
    previous: Final[int] = os.umask(mask)
    try:
        data: Final[AppData] = make_app_data(None, read_only=False, env={})
    finally:
        os.umask(previous)
    assert (home.stat().st_mode & 0o777, cache.stat().st_mode & 0o777, folder.stat().st_mode & 0o777) == (
        0o755,
        0o700,
        0o700,
    )
    assert str(data) == str(folder)


def test_app_data_default_parent_collision_uses_temporary(tmp_path: Path, mocker: MockerFixture) -> None:
    cache: Final[Path] = tmp_path / ".cache"
    folder: Final[Path] = cache / "virtualenv"
    mocker.patch("virtualenv.app_data.cache_migration.user_cache_dir", autospec=True, return_value=str(folder))
    mocker.patch("virtualenv.app_data.cache_migration.user_data_dir", autospec=True, return_value=str(tmp_path / "old"))
    mkdir = os.mkdir

    def collide(path: str, mode: int = 0o777) -> None:
        if path == str(cache):
            cache.write_text("blocked", encoding="utf-8")
            raise FileExistsError(path)
        mkdir(path, mode)

    mocker.patch("virtualenv.app_data.cache_migration.os.mkdir", autospec=True, side_effect=collide)
    data: Final[AppData] = make_app_data(None, read_only=False, env={})
    try:
        assert (data.transient, cache.read_text(encoding="utf-8")) == (True, "blocked")
    finally:
        data.close()


@pytest.mark.skipif(os.name != "nt", reason="Windows drive roots")
@pytest.mark.timeout(10)
def test_app_data_default_missing_drive_uses_temporary(tmp_path: Path, mocker: MockerFixture) -> None:
    mocker.patch("virtualenv.app_data.cache_migration.user_cache_dir", autospec=True, return_value="Z:\\virtualenv")
    mocker.patch("virtualenv.app_data.cache_migration.user_data_dir", autospec=True, return_value=str(tmp_path / "old"))
    exists = os.path.exists

    def missing_drive(path: str | os.PathLike[str]) -> bool:
        return not str(path).startswith("Z:\\") and exists(path)

    mocker.patch("virtualenv.app_data.cache_migration.os.path.exists", autospec=True, side_effect=missing_drive)
    mocker.patch("virtualenv.app_data.os.access", autospec=True, return_value=False)
    data: Final[AppData] = make_app_data(None, read_only=False, env={})
    try:
        assert data.transient
    finally:
        data.close()


@pytest.mark.skipif(os.name != "posix", reason="POSIX directory permission bits")
@pytest.mark.parametrize("mode", [pytest.param(0o700, id="private"), pytest.param(0o2775, id="shared-setgid")])
def test_app_data_default_existing_parent_keeps_mode(tmp_path: Path, mocker: MockerFixture, mode: int) -> None:
    cache: Final[Path] = tmp_path / ".cache"
    cache.mkdir()
    cache.chmod(mode)
    folder: Final[Path] = cache / "virtualenv"
    mocker.patch("virtualenv.app_data.cache_migration.user_cache_dir", autospec=True, return_value=str(folder))
    mocker.patch("virtualenv.app_data.cache_migration.user_data_dir", autospec=True, return_value=str(tmp_path / "old"))

    data: Final[AppData] = make_app_data(None, read_only=False, env={})

    assert (cache.stat().st_mode & 0o7777, folder.stat().st_mode & 0o777, str(data)) == (
        mode,
        0o700,
        str(folder),
    )


@pytest.mark.skipif(os.name != "posix", reason="POSIX directory permission bits")
def test_app_data_explicit_missing_parent_keeps_umask(tmp_path: Path) -> None:
    parent: Final[Path] = tmp_path / "shared"
    folder: Final[Path] = parent / "cache"
    previous: Final[int] = os.umask(0o002)
    try:
        data: Final[AppData] = make_app_data(str(folder), read_only=False, env={})
    finally:
        os.umask(previous)
    assert (parent.stat().st_mode & 0o777, folder.stat().st_mode & 0o777, str(data)) == (
        0o775,
        0o775,
        str(folder),
    )


@pytest.mark.skipif(os.name != "posix", reason="POSIX directory permission bits")
@pytest.mark.parametrize("env", _DEFAULT_APP_DATA_ENVS)
@pytest.mark.parametrize("mode", [0o777, 0o775, 0o755, 0o750, 0o711])
def test_app_data_default_permissions_existing(
    app_data_default: Path, env: dict[str, str], mode: int, caplog: pytest.LogCaptureFixture
) -> None:
    app_data_default.mkdir()
    app_data_default.chmod(mode)
    data: Final[AppDataDiskFolder] = _make_app_data_with_zero_umask(env)
    assert (str(data), app_data_default.stat().st_mode & 0o777) == (str(app_data_default), 0o700)
    assert "use setgid sharing or an explicit --app-data path" in caplog.text


@pytest.mark.parametrize("env", _DEFAULT_APP_DATA_ENVS)
def test_app_data_default_reset_recreates_root(app_data_default: Path, env: dict[str, str]) -> None:
    data: Final[AppDataDiskFolder] = make_app_data(None, read_only=False, env=env)
    (app_data_default / "old").touch()
    data.reset()
    assert (app_data_default.is_dir(), (app_data_default / "old").exists()) == (True, False)


@pytest.mark.skipif(os.name != "posix", reason="POSIX directory permission bits")
@pytest.mark.parametrize("env", _DEFAULT_APP_DATA_ENVS)
def test_app_data_default_reset_keeps_private_root(app_data_default: Path, env: dict[str, str]) -> None:
    data: Final[AppDataDiskFolder] = _make_app_data_with_zero_umask(env)
    (app_data_default / "old").touch()
    previous: Final[int] = os.umask(0)
    try:
        data.reset()
        with data.lock.lock_for_key("new"):
            assert (app_data_default.stat().st_mode & 0o777, (app_data_default / "old").exists()) == (0o700, False)
    finally:
        os.umask(previous)


@pytest.mark.skipif(os.name != "posix", reason="POSIX directory permission bits")
def test_app_data_default_reset_after_external_removal(app_data_default: Path) -> None:
    data: Final[AppDataDiskFolder] = make_app_data(None, read_only=False, env={})
    app_data_default.rmdir()
    data.reset()
    assert app_data_default.stat().st_mode & 0o777 == 0o700


@pytest.mark.skipif(os.name != "posix", reason="POSIX directory permission bits")
def test_app_data_default_reset_recreates_private_parent(tmp_path: Path, mocker: MockerFixture) -> None:
    parent: Final[Path] = tmp_path / "cache-home"
    folder: Final[Path] = parent / "cache"
    mocker.patch("virtualenv.app_data.cache_migration.user_cache_dir", autospec=True, return_value=str(folder))
    mocker.patch("virtualenv.app_data.cache_migration.user_data_dir", autospec=True, return_value=str(tmp_path / "old"))
    data: Final[AppDataDiskFolder] = make_app_data(None, read_only=False, env={})
    folder.rmdir()
    parent.rmdir()
    previous: Final[int] = os.umask(0)
    try:
        data.reset()
    finally:
        os.umask(previous)
    assert (parent.stat().st_mode & 0o777, folder.stat().st_mode & 0o777) == (0o700, 0o700)


@pytest.mark.skipif(os.name != "posix", reason="POSIX group permissions")
def test_app_data_default_reset_preserves_setgid_group(app_data_default: Path) -> None:
    app_data_default.mkdir()
    app_data_default.chmod(0o2775)
    data: Final[AppDataDiskFolder] = make_app_data(None, read_only=False, env={})
    group: Final[int] = app_data_default.stat().st_gid
    data.reset()
    assert (app_data_default.stat().st_mode & 0o7777, app_data_default.stat().st_gid) == (0o2770, group)


@pytest.mark.skipif(os.name != "posix", reason="POSIX group permissions")
def test_app_data_default_reset_group_restore_failure_keeps_private_root(
    app_data_default: Path, mocker: MockerFixture, caplog: pytest.LogCaptureFixture
) -> None:
    app_data_default.mkdir()
    app_data_default.chmod(0o2775)
    data: Final[AppDataDiskFolder] = make_app_data(None, read_only=False, env={})
    mocker.patch("virtualenv.app_data.via_disk_folder.os.chown", autospec=True, side_effect=PermissionError)
    data.reset()
    assert (app_data_default.stat().st_mode & 0o7777, "keeping reset app data folder" in caplog.text) == (0o700, True)


def test_app_data_explicit_reset_leaves_folder_absent(tmp_path: Path) -> None:
    data: Final[AppData] = make_app_data(str(tmp_path / "cache"), read_only=False, env={})
    data.reset()
    assert not (tmp_path / "cache").exists()


@pytest.mark.skipif(os.name != "posix", reason="POSIX directory permission bits")
def test_app_data_argument_permissions(tmp_path: Path) -> None:
    tmp_path.chmod(0o775)
    data: Final[AppData] = make_app_data(str(tmp_path), read_only=False, env={})
    assert (str(data), tmp_path.stat().st_mode & 0o777) == (str(tmp_path), 0o775)


@pytest.mark.skipif(os.name != "posix", reason="POSIX directory permission bits")
def test_app_data_environment_permissions(tmp_path: Path) -> None:
    tmp_path.chmod(0o775)
    data: Final[AppData] = make_app_data(None, read_only=False, env={"VIRTUALENV_OVERRIDE_APP_DATA": str(tmp_path)})
    assert (str(data), tmp_path.stat().st_mode & 0o777) == (str(tmp_path), 0o775)


def test_app_data_read_only_does_not_create(app_data_default: Path) -> None:
    with pytest.raises(RuntimeError, match="does not exist"):
        make_app_data(None, read_only=True, env={})
    assert not app_data_default.exists()


@pytest.mark.skipif(os.name != "posix", reason="POSIX directory permission bits")
def test_app_data_read_only_permissions(app_data_default: Path) -> None:
    app_data_default.mkdir()
    app_data_default.chmod(0o775)
    data: Final[AppData] = make_app_data(None, read_only=True, env={})
    assert (str(data), app_data_default.stat().st_mode & 0o777) == (str(app_data_default), 0o775)


def test_app_data_default_writable(app_data_default: Path) -> None:
    data: Final[AppData] = make_app_data(None, read_only=False, env={})
    target: Final[Path] = app_data_default / "entry"
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
    mocker.patch("virtualenv.app_data.os.chmod", autospec=True, side_effect=PermissionError)
    data: Final[AppData] = make_app_data(None, read_only=False, env={})
    try:
        assert isinstance(data, TempAppData)
        assert str(data) != str(app_data_default)
    finally:
        data.close()


@pytest.mark.parametrize("writable", [pytest.param(False, id="unwritable"), pytest.param(True, id="writable")])
def test_app_data_explicit_create_failure(tmp_path: Path, mocker: MockerFixture, writable: bool) -> None:
    mocker.patch("virtualenv.app_data.os.makedirs", autospec=True, side_effect=PermissionError)
    mocker.patch("virtualenv.app_data.os.access", autospec=True, return_value=writable)
    data: Final[AppData] = make_app_data(str(tmp_path), read_only=False, env={})
    try:
        assert (data.transient, str(data) == str(tmp_path)) == (not writable, writable)
    finally:
        data.close()


@pytest.mark.parametrize(
    "no_home",
    [
        pytest.param("~/.cache/virtualenv", id="unexpanded"),
        pytest.param(RuntimeError("no home directory"), id="unavailable"),
    ],
)
def test_app_data_without_home_uses_temporary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mocker: MockerFixture, no_home: str | RuntimeError
) -> None:
    monkeypatch.chdir(tmp_path)
    mocker.patch("virtualenv.app_data.cache_migration.user_cache_dir", autospec=True, side_effect=[no_home])
    mocker.patch(
        "virtualenv.app_data.cache_migration.user_data_dir", autospec=True, return_value="~/.local/share/virtualenv"
    )

    data = make_app_data(None, read_only=False, env={})
    try:
        assert (isinstance(data, TempAppData), (tmp_path / "~/.cache/virtualenv").exists()) == (True, False)
    finally:
        data.close()


@pytest.mark.parametrize(
    "no_home",
    [
        pytest.param("~/.local/share/virtualenv", id="unexpanded"),
        pytest.param(RuntimeError("no home directory"), id="unavailable"),
    ],
)
def test_app_data_does_not_migrate_without_old_home(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mocker: MockerFixture, no_home: str | RuntimeError
) -> None:
    old_dir = tmp_path / "~/.local/share/virtualenv"
    old_dir.mkdir(parents=True)
    (old_dir / "marker").write_text("old", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    new_dir = tmp_path / "cache/virtualenv"
    mocker.patch("virtualenv.app_data.cache_migration.user_cache_dir", autospec=True, return_value=str(new_dir))
    mocker.patch("virtualenv.app_data.cache_migration.user_data_dir", autospec=True, side_effect=[no_home])

    data = make_app_data(None, read_only=False, env={})

    assert (str(data), (old_dir / "marker").read_text(encoding="utf-8"), (new_dir / "marker").exists()) == (
        str(new_dir),
        "old",
        False,
    )


def test_app_data_read_only_without_home(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mocker: MockerFixture
) -> None:
    monkeypatch.chdir(tmp_path)
    mocker.patch(
        "virtualenv.app_data.cache_migration.user_cache_dir", autospec=True, return_value="~/.cache/virtualenv"
    )

    with pytest.raises(RuntimeError, match="read-only app data requires an explicit cache path"):
        make_app_data(None, read_only=True, env={})
    assert not (tmp_path / "~/.cache/virtualenv").exists()


def test_app_data_explicit_without_home(tmp_path: Path, mocker: MockerFixture) -> None:
    mocker.patch(
        "virtualenv.app_data.cache_migration.user_cache_dir", autospec=True, side_effect=RuntimeError("no home")
    )

    data = make_app_data(None, read_only=False, env={"VIRTUALENV_OVERRIDE_APP_DATA": str(tmp_path / "cache")})

    assert str(data) == str(tmp_path / "cache")


def test_app_data_ignores_relative_default_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mocker: MockerFixture
) -> None:
    (planted := tmp_path / "rel/virtualenv/wheel").mkdir(parents=True)
    monkeypatch.chdir(tmp_path)
    mocker.patch("virtualenv.app_data.cache_migration.user_cache_dir", autospec=True, return_value="rel/virtualenv")

    data = make_app_data(None, read_only=False, env={})
    try:
        assert (data.transient, str(data).startswith(str(planted.parent))) == (True, False)
    finally:
        data.close()


@pytest.mark.skipif(os.name != "posix", reason="POSIX directory permission bits")
def test_app_data_config_only_legacy_dir_needs_no_migration(tmp_path: Path, mocker: MockerFixture) -> None:
    old_dir: Final[Path] = tmp_path / "config"
    old_dir.mkdir()
    (old_dir / "virtualenv.ini").touch()
    old_dir.chmod(0o555)
    new_dir: Final[Path] = tmp_path / "cache"
    mocker.patch("virtualenv.app_data.cache_migration.user_cache_dir", autospec=True, return_value=str(new_dir))
    mocker.patch("virtualenv.app_data.cache_migration.user_data_dir", autospec=True, return_value=str(old_dir))
    try:
        data = make_app_data(None, read_only=False, env={})
    finally:
        old_dir.chmod(0o755)

    assert (str(data), sorted(entry.name for entry in old_dir.iterdir())) == (str(new_dir), ["virtualenv.ini"])


@pytest.mark.skipif(os.name != "posix", reason="POSIX directory permission bits")
def test_app_data_private_cache_does_not_warn(app_data_default: Path, caplog: pytest.LogCaptureFixture) -> None:
    app_data_default.mkdir(mode=0o700)

    make_app_data(None, read_only=False, env={})

    assert "restricted default cache" not in caplog.text


@pytest.mark.skipif(os.name != "posix", reason="POSIX directory permission bits")
def test_config_cache_migration_missing_parent_private(tmp_path: Path, mocker: MockerFixture) -> None:
    old_dir: Final[Path] = tmp_path / "old"
    old_dir.mkdir()
    (old_dir / "virtualenv.ini").touch()
    (old_dir / "wheel").mkdir()
    parent: Final[Path] = tmp_path / ".cache"
    new_dir: Final[Path] = parent / "virtualenv"
    mocker.patch("virtualenv.app_data.cache_migration.user_cache_dir", autospec=True, return_value=str(new_dir))
    mocker.patch("virtualenv.app_data.cache_migration.user_data_dir", autospec=True, return_value=str(old_dir))
    previous: Final[int] = os.umask(0)
    try:
        data: Final[AppData] = make_app_data(None, read_only=False, env={})
    finally:
        os.umask(previous)

    assert (parent.stat().st_mode & 0o777, str(data), (new_dir / "wheel").is_dir()) == (0o700, str(new_dir), True)


@pytest.fixture
def app_data_default(tmp_path: Path, mocker: MockerFixture, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(tmp_path)  # a blank override resolved to the working directory, so keep that inside tmp_path
    folder: Final[Path] = tmp_path / "cache"
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
    source: Final[Path] = tmp_path / "source"
    source.mkdir()
    payload: Final[Path] = source / "entry"
    payload.write_bytes(b"copied bytes")
    payload.chmod(source_mode)
    destination: Final[Path] = tmp_path / "destination"
    previous: Final[int] = os.umask(mask)
    try:
        copy(source / source_rel, destination)
    finally:
        os.umask(previous)
    result: Final[Path] = destination / result_rel
    assert (result.read_bytes(), result.stat().st_mode & 0o777) == (b"copied bytes", expected)


@pytest.mark.skipif(os.name != "posix", reason="POSIX file permission bits")
@pytest.mark.parametrize(
    ("original", "expected"),
    [
        pytest.param(0o600, 0o400, id="private"),
        pytest.param(0o660, 0o440, id="group-private"),
        pytest.param(0o644, 0o444, id="readable"),
    ],
)
def test_set_tree_keeps_existing_read_restrictions(tmp_path: Path, original: int, expected: int) -> None:
    package: Final[Path] = tmp_path / "package"
    package.mkdir()
    image: Final[Path] = package / "image.py"
    image.write_text("private image", encoding="utf-8")
    image.chmod(original)

    set_tree(tmp_path, stat=0o444)

    assert (image.stat().st_mode & 0o777, image.read_text(encoding="utf-8")) == (expected, "private image")


@pytest.mark.parametrize("layout", [pytest.param(("entry", ""), id="file"), pytest.param(("", "entry"), id="tree")])
def test_copy_replaces_contents(tmp_path: Path, layout: tuple[str, str]) -> None:
    source_rel, result_rel = layout
    source: Final[Path] = tmp_path / "source"
    source.mkdir()
    (source / "entry").write_bytes(b"new")
    destination: Final[Path] = tmp_path / "destination"
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
    source: Final[Path] = tmp_path / "source"
    source.mkdir()
    target: Final[Path] = source / "target"
    target.mkdir()
    (target / "inside.txt").write_text("content", encoding="utf-8")
    (source / "link_to_file").symlink_to(target / "inside.txt")
    (source / "link_to_dir").symlink_to(target, target_is_directory=True)

    destination: Final[Path] = tmp_path / "destination"
    copy(source, destination)

    assert (
        (destination / "link_to_file").read_text(encoding="utf-8"),
        (destination / "link_to_dir" / "inside.txt").read_text(encoding="utf-8"),
    ) == ("content", "content")


@pytest.mark.skipif(not fs_supports_symlink(), reason="symlinks are unavailable")
@pytest.mark.parametrize("target", [pytest.param(".", id="itself"), pytest.param("..", id="above-source")])
def test_copy_does_not_expand_a_symlinked_directory_pointing_at_a_parent(tmp_path: Path, target: str) -> None:
    source: Final[Path] = tmp_path / "source"
    source.mkdir()
    (source / "entry.txt").write_text("content", encoding="utf-8")
    (source / "loop").symlink_to(target, target_is_directory=True)

    destination: Final[Path] = tmp_path / "destination"
    copy(source, destination)

    assert sorted(i.name for i in destination.iterdir()) == ["entry.txt"]


@pytest.mark.skipif(sys.platform != "linux", reason="minimal Linux builds can omit ctypes")
def test_command_line_import_without_ctypes() -> None:
    result: Final[tuple[int, str, str]] = run_cmd([
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
    folder: Final[Path] = tmp_path / "folder"
    folder.mkdir()
    source: Final[Path] = folder / "read-only"
    source.touch()
    source.chmod(S_IREAD)
    kernel: Final[ctypes.CDLL] = ctypes.WinDLL("kernel32", use_last_error=True)
    mocker.patch.object(kernel, operation, autospec=True, return_value=failure_return())
    mocker.patch("ctypes.WinDLL", autospec=True, return_value=kernel)
    mocker.patch("ctypes.get_last_error", autospec=True, return_value=5)
    with pytest.raises(PermissionError, match="WinError 5"):
        safe_delete(folder)
    assert source.stat().st_mode & S_IWUSR == 0
    source.chmod(S_IREAD | S_IWUSR)


@pytest.mark.skipif(not fs_supports_symlink(), reason="symlinks are unavailable")
def test_safe_delete_does_not_chmod_link_target(tmp_path: Path, mocker: MockerFixture) -> None:
    source: Final[Path] = tmp_path / "read-only"
    source.write_text("unchanged", encoding="utf-8")
    source.chmod(S_IREAD)
    mode: Final[int] = source.stat().st_mode
    folder: Final[Path] = tmp_path / "folder"
    folder.mkdir()
    (folder / "link").symlink_to(source)
    unlink: Final[MockType] = mocker.patch(
        "os.unlink", autospec=True, side_effect=PermissionError(EACCES, "entry is busy")
    )
    try:
        with pytest.raises(PermissionError, match="entry is busy"):
            safe_delete(folder)
    finally:
        mocker.stop(unlink)
    assert source.stat().st_mode == mode


def test_write_file_creates_missing_file(tmp_path: Path) -> None:
    path: Final[Path] = tmp_path / "generated"
    write_file(path, b"generated")
    assert path.read_bytes() == b"generated"


def test_write_file_replaces_content(tmp_path: Path) -> None:
    path: Final[Path] = tmp_path / "generated"
    path.write_bytes(b"previous")
    write_file(path, b"generated")
    assert path.read_bytes() == b"generated"


def test_write_file_replaces_read_only_file(tmp_path: Path) -> None:
    (path := tmp_path / "generated").write_bytes(b"previous")
    path.chmod(S_IREAD)
    write_file(path, b"generated")
    assert path.read_bytes() == b"generated"


@pytest.mark.skipif(os.name != "nt", reason="Windows file attributes")
def test_write_file_keeps_hard_linked_file_read_only(tmp_path: Path) -> None:
    (source := tmp_path / "source").write_bytes(b"previous")
    os.link(source, path := tmp_path / "generated")
    source.chmod(S_IREAD)
    write_file(path, b"generated")
    assert (source.read_bytes(), bool(source.stat().st_file_attributes & 1), path.read_bytes()) == (
        b"previous",
        True,
        b"generated",
    )


@pytest.fixture
def legacy_windows_delete(mocker: MockerFixture) -> None:
    kernel: Final[ctypes.CDLL] = ctypes.WinDLL("kernel32", use_last_error=True)
    native_set: Final[Callable[[int, int, ctypes.c_void_p, int], int]] = kernel.SetFileInformationByHandle

    def set_info(handle: int, info_class: int, info: ctypes.c_void_p, size: int) -> int:
        if info_class == 21:
            ctypes.set_last_error(87)
            return 0
        return native_set(handle, info_class, info, size)

    mocker.patch.object(kernel, "SetFileInformationByHandle", autospec=True, side_effect=set_info)
    mocker.patch("ctypes.WinDLL", autospec=True, return_value=kernel)


@pytest.mark.skipif(os.name != "nt", reason="Windows file attributes")
@pytest.mark.usefixtures("legacy_windows_delete")
def test_write_file_replaces_read_only_file_without_disposition_ex(tmp_path: Path) -> None:
    (path := tmp_path / "generated").write_bytes(b"previous")
    path.chmod(S_IREAD)
    write_file(path, b"generated")
    assert path.read_bytes() == b"generated"


@pytest.mark.skipif(os.name != "nt", reason="Windows file attributes")
@pytest.mark.usefixtures("legacy_windows_delete")
def test_write_file_refuses_hard_link_without_disposition_ex(tmp_path: Path) -> None:
    (source := tmp_path / "source").write_bytes(b"previous")
    os.link(source, path := tmp_path / "generated")
    source.chmod(S_IREAD)
    with pytest.raises(OSError, match="cannot delete read-only hard link"):
        write_file(path, b"generated")
    assert (source.read_bytes(), path.read_bytes(), bool(source.stat().st_file_attributes & 1)) == (
        b"previous",
        b"previous",
        True,
    )


@pytest.mark.skipif(os.name != "nt", reason="Windows file attributes")
@pytest.mark.parametrize(
    "failure",
    [
        pytest.param("standard", id="read-link-count"),
        pytest.param("basic", id="clear-attribute"),
        pytest.param("disposition", id="mark-for-deletion"),
    ],
)
def test_legacy_delete_reports_errors_without_changing_read_only_file(
    tmp_path: Path, mocker: MockerFixture, failure: str
) -> None:
    kernel: Final[ctypes.CDLL] = ctypes.WinDLL("kernel32", use_last_error=True)
    native_get: Final[Callable[[int, int, ctypes.c_void_p, int], int]] = kernel.GetFileInformationByHandleEx
    native_set: Final[Callable[[int, int, ctypes.c_void_p, int], int]] = kernel.SetFileInformationByHandle

    def get_info(handle: int, info_class: int, info: ctypes.c_void_p, size: int) -> int:
        if failure == "standard" and info_class == 1:
            ctypes.set_last_error(5)
            return 0
        return native_get(handle, info_class, info, size)

    def set_info(handle: int, info_class: int, info: ctypes.c_void_p, size: int) -> int:
        if info_class == 21:
            ctypes.set_last_error(87)
            return 0
        if (failure == "basic" and info_class == 0) or (failure == "disposition" and info_class == 4):
            ctypes.set_last_error(5)
            return 0
        return native_set(handle, info_class, info, size)

    mocker.patch.object(kernel, "GetFileInformationByHandleEx", autospec=True, side_effect=get_info)
    mocker.patch.object(kernel, "SetFileInformationByHandle", autospec=True, side_effect=set_info)
    mocker.patch("ctypes.WinDLL", autospec=True, return_value=kernel)
    (path := tmp_path / "generated").write_bytes(b"previous")
    path.chmod(S_IREAD)
    with pytest.raises(PermissionError, match="WinError 5"):
        write_file(path, b"generated")
    assert (path.read_bytes(), bool(path.stat().st_file_attributes & 1)) == (b"previous", True)


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
    folder: Final[Path] = tmp_path / "env" / "lib" / "python"
    ensure_within(tmp_path / "env", folder)
    assert folder.is_dir()


def test_environment_directories_keep_existing_nested_path(tmp_path: Path) -> None:
    folder: Final[Path] = tmp_path / "env" / "lib" / "python"
    folder.mkdir(parents=True)
    ensure_within(tmp_path / "env", folder)
    assert folder.is_dir()


def test_environment_directories_reject_regular_file(tmp_path: Path) -> None:
    folder: Final[Path] = tmp_path / "file"
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
    target: Final[Path] = tmp_path / "stored"
    link: Final[Path] = tmp_path / "link"
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
    target: Final[Path] = tmp_path / "stored"
    target.mkdir()
    link: Final[Path] = tmp_path / "link"
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
    target: Final[Path] = tmp_path / "stored"
    target.mkdir()
    link: Final[Path] = tmp_path / "link"
    subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(target)], check=True, capture_output=True)
    ensure_within(tmp_path, link)
    assert (link.resolve(), f"replace environment directory junction {link}" in caplog.text) == (link, True)


def test_run_fail(tmp_path) -> None:
    result = run_cmd([str(tmp_path)])
    assert type(result) is tuple
    code, out, err = result
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


@pytest.mark.skipif(os.name != "nt", reason="Windows file attributes")
def test_safe_delete_keeps_hard_linked_file_read_only(tmp_path: Path) -> None:
    (source := tmp_path / "source").write_bytes(b"previous")
    (folder := tmp_path / "folder").mkdir()
    os.link(source, folder / "linked")
    source.chmod(S_IREAD)
    safe_delete(folder)
    assert (folder.exists(), source.read_bytes(), bool(source.stat().st_file_attributes & 1)) == (
        False,
        b"previous",
        True,
    )


@pytest.mark.skipif(os.name != "nt", reason="Windows read-only directories")
def test_safe_delete_removes_read_only_directory(tmp_path: Path) -> None:
    (folder := tmp_path / "folder").mkdir()
    (nested := folder / "nested").mkdir()
    nested.chmod(S_IREAD)

    safe_delete(folder)

    assert not folder.exists()


@pytest.mark.skipif(os.name != "nt", reason="Windows read-only directories")
def test_safe_delete_removes_read_only_directory_with_file(tmp_path: Path) -> None:
    (folder := tmp_path / "folder").mkdir()
    (nested := folder / "nested").mkdir()
    (file := nested / "file").write_bytes(b"contents")
    file.chmod(S_IREAD)
    nested.chmod(S_IREAD)

    safe_delete(folder)

    assert not folder.exists()


def test_safe_delete_missing_path_is_noop(tmp_path: Path) -> None:
    safe_delete(tmp_path / "does-not-exist")  # --reset-app-data before anything was cached

    assert list(tmp_path.iterdir()) == []


@pytest.mark.skipif(sys.platform != "win32", reason="only Windows blocks deleting an open file")
def test_safe_delete_surfaces_undeletable_entries(tmp_path: Path) -> None:
    target = tmp_path / "target"
    target.mkdir()
    busy = target / "busy.txt"
    busy.write_text("x", encoding="utf-8")

    with busy.open(encoding="utf-8"), pytest.raises(OSError, match="busy"):
        safe_delete(target)


@pytest.mark.skipif(os.name != "nt", reason="Windows short path API")
def test_get_short_path_name_reports_missing_path(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        get_short_path_name(str(tmp_path / "missing"))

    assert Path(get_short_path_name(str(tmp_path))).samefile(tmp_path)


@pytest.mark.skipif(os.name != "nt", reason="Windows extended-length paths")
@pytest.mark.parametrize(
    ("given", "expected"),
    [
        pytest.param(r"C:\cache\image\..\wheel", r"\\?\C:\cache\wheel", id="drive"),
        pytest.param(r"\\server\share\cache", r"\\?\UNC\server\share\cache", id="share"),
        pytest.param(r"\\?\C:\cache\wheel", r"\\?\C:\cache\wheel", id="extended"),
        pytest.param(r"\\.\C:\cache\wheel", r"\\.\C:\cache\wheel", id="device"),
    ],
)
def test_safe_delete_hands_rmtree_the_extended_length_path(mocker: MockerFixture, given: str, expected: str) -> None:
    rmtree: Final[MockType] = mocker.patch("shutil.rmtree", autospec=True)

    safe_delete(Path(given))

    assert rmtree.call_args.args[0] == expected


@pytest.mark.skipif(os.name != "nt", reason="Windows MAX_PATH")
def test_safe_delete_removes_files_past_max_path(tmp_path: Path) -> None:
    target: Final[Path] = tmp_path / "target"
    # a seed image built through its short path holds files that only its long path reaches, past MAX_PATH
    deep: Final[Path] = Path(f"\\\\?\\{target}", "d" * 120, "e" * 120)
    deep.mkdir(parents=True)
    cached: Final[Path] = deep / "wheel.py"
    cached.write_text("cached", encoding="utf-8")
    cached.chmod(S_IREAD)

    safe_delete(target)

    assert list(tmp_path.iterdir()) == []


def _junction(link: Path, target: Path) -> None:
    subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(target)], check=True, capture_output=True)


def _directory_symlink(link: Path, target: Path) -> None:
    link.symlink_to(target, target_is_directory=True)


_DIRECTORY_LINKS: Final[list[pytest.ParameterSet]] = [
    pytest.param(_junction, marks=pytest.mark.skipif(os.name != "nt", reason="Windows junctions"), id="junction"),
    pytest.param(
        _directory_symlink,
        marks=pytest.mark.skipif(not fs_supports_symlink(), reason="symlinks are unavailable"),
        id="symlink",
    ),
]


@pytest.fixture
def kept(tmp_path: Path) -> Path:
    outside: Final[Path] = tmp_path / "outside"
    outside.mkdir()
    kept: Final[Path] = outside / "kept.txt"
    kept.write_text("kept", encoding="utf-8")
    kept.chmod(S_IREAD)
    return kept


@pytest.mark.parametrize("make_link", _DIRECTORY_LINKS)
def test_safe_delete_removes_a_directory_link_without_following_it(
    tmp_path: Path, kept: Path, make_link: Callable[[Path, Path], None]
) -> None:
    target: Final[Path] = tmp_path / "target"
    target.mkdir()
    make_link(target / "link", kept.parent)

    safe_delete(target)

    assert (target.exists(), kept.read_text(encoding="utf-8"), kept.stat().st_mode & S_IWUSR) == (False, "kept", 0)


@pytest.mark.parametrize("make_link", _DIRECTORY_LINKS)
def test_safe_delete_refuses_a_directory_link_as_the_root(
    tmp_path: Path, kept: Path, make_link: Callable[[Path, Path], None]
) -> None:
    link: Final[Path] = tmp_path / "link"
    make_link(link, kept.parent)

    with pytest.raises(OSError) as raised:  # ruff: ignore[pytest-raises-too-broad] # str() differs on POSIX
        safe_delete(link)

    assert (raised.value.args, os.path.lexists(link), kept.read_text(encoding="utf-8")) == (
        ("Cannot call rmtree on a symbolic link",),
        True,
        "kept",
    )


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


@pytest.mark.parametrize("depth", [1, 2, 3])
def test_nested_file_lock_releases_thread_lock(tmp_path: Path, mocker: MockerFixture, depth: int) -> None:
    lock = ReentrantFileLock(tmp_path)
    create_lock = mocker.spy(lock, "_create_lock")

    def acquire_from_another_thread() -> None:
        counted_lock.acquire(timeout=1)
        counted_lock.release()

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        with lock.lock_for_key("target"):
            with ExitStack() as contexts:
                for _ in range(depth - 1):
                    contexts.enter_context(lock.lock_for_key("target"))
                # A waiting thread can retain this same counted lock after it leaves the store.
                counted_lock = create_lock.spy_return
            # Releasing inner contexts must still leave the outer context protected.
            with pytest.raises(Timeout):
                executor.submit(acquire_from_another_thread).result(timeout=5)
        executor.submit(acquire_from_another_thread).result(timeout=5)


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


@pytest.mark.skipif(os.name != "posix", reason="POSIX directory permission bits")
def test_cache_migration_missing_parent_private(tmp_path: Path, mocker: MockerFixture) -> None:
    old_dir: Final[Path] = tmp_path / "old"
    old_dir.mkdir()
    (old_dir / "data.txt").write_text("cached", encoding="utf-8")
    parent: Final[Path] = tmp_path / ".cache"
    new_dir: Final[Path] = parent / "virtualenv"
    mocker.patch("virtualenv.app_data.cache_migration.user_cache_dir", autospec=True, return_value=str(new_dir))
    mocker.patch("virtualenv.app_data.cache_migration.user_data_dir", autospec=True, return_value=str(old_dir))
    previous: Final[int] = os.umask(0o002)
    try:
        data: Final[AppData] = make_app_data(None, read_only=False, env={})
    finally:
        os.umask(previous)
    assert (
        parent.stat().st_mode & 0o777,
        str(data),
        old_dir.exists(),
        (new_dir / "data.txt").read_text(encoding="utf-8"),
    ) == (0o700, str(new_dir), False, "cached")


@pytest.mark.skipif(os.name != "posix", reason="POSIX directory permission bits")
@pytest.mark.parametrize(
    ("extra_files", "entry", "selected"),
    [
        pytest.param({}, "data.txt", "original", id="plain"),
        pytest.param({"virtualenv.ini": "[virtualenv]\n"}, "wheel/pip.whl", ".cache/virtualenv", id="config"),
    ],
)
def test_cache_migration_linked_missing_parent_private(
    tmp_path: Path, mocker: MockerFixture, extra_files: dict[str, str], entry: str, selected: str
) -> None:
    original: Final[Path] = tmp_path / "original"
    original.mkdir()
    for name, content in extra_files.items():
        (original / name).write_text(content, encoding="utf-8")
    (original / entry).parent.mkdir(exist_ok=True)
    (original / entry).write_text("cached", encoding="utf-8")
    old_dir: Final[Path] = tmp_path / "old"
    old_dir.symlink_to(original, target_is_directory=True)
    parent: Final[Path] = tmp_path / ".cache"
    new_dir: Final[Path] = parent / "virtualenv"
    mocker.patch("virtualenv.app_data.cache_migration.user_cache_dir", autospec=True, return_value=str(new_dir))
    mocker.patch("virtualenv.app_data.cache_migration.user_data_dir", autospec=True, return_value=str(old_dir))
    previous: Final[int] = os.umask(0o002)
    try:
        data: Final[AppData] = make_app_data(None, read_only=False, env={})
    finally:
        os.umask(previous)
    assert (parent.stat().st_mode & 0o777, str(data), (new_dir / entry).read_text(encoding="utf-8")) == (
        0o700,
        str(tmp_path / selected),
        "cached",
    )


@pytest.mark.skipif(os.name != "posix", reason="POSIX directory permission bits")
@pytest.mark.parametrize("mask", [0o002, 0o000])
def test_cache_migration_shared_parent_preserves_group(tmp_path: Path, mocker: MockerFixture, mask: int) -> None:
    old_dir: Final[Path] = tmp_path / "old"
    old_dir.mkdir()
    old_dir.chmod(0o2775)
    parent: Final[Path] = tmp_path / ".cache"
    new_dir: Final[Path] = parent / "virtualenv"
    mocker.patch("virtualenv.app_data.cache_migration.user_cache_dir", autospec=True, return_value=str(new_dir))
    mocker.patch("virtualenv.app_data.cache_migration.user_data_dir", autospec=True, return_value=str(old_dir))
    previous: Final[int] = os.umask(mask)
    try:
        data: Final[AppData] = make_app_data(None, read_only=False, env={})
    finally:
        os.umask(previous)
    assert (parent.stat().st_mode & 0o777, new_dir.stat().st_mode & 0o7777, str(data)) == (
        0o710,
        0o2770,
        str(new_dir),
    )


@pytest.mark.skipif(os.name != "posix", reason="POSIX directory permission bits")
@pytest.mark.parametrize(
    ("old_mode", "expected_modes"),
    [
        pytest.param(0o755, (0o700, 0o700), id="ordinary"),
        pytest.param(0o2775, (0o2770, 0o2770), id="shared-setgid"),
    ],
)
def test_cache_nested_migration_missing_parent_permissions(
    tmp_path: Path, mocker: MockerFixture, old_mode: int, expected_modes: tuple[int, int]
) -> None:
    old_dir: Final[Path] = tmp_path / "old"
    old_dir.mkdir()
    old_dir.chmod(old_mode)
    (old_dir / "data.txt").write_text("cached", encoding="utf-8")
    parent: Final[Path] = old_dir / "Cache"
    new_dir: Final[Path] = parent / "virtualenv"
    mocker.patch("virtualenv.app_data.cache_migration.user_cache_dir", autospec=True, return_value=str(new_dir))
    mocker.patch("virtualenv.app_data.cache_migration.user_data_dir", autospec=True, return_value=str(old_dir))
    previous: Final[int] = os.umask(0o000)
    try:
        data: Final[AppData] = make_app_data(None, read_only=False, env={})
    finally:
        os.umask(previous)
    assert (
        parent.stat().st_mode & 0o7777,
        new_dir.stat().st_mode & 0o7777,
        parent.stat().st_gid,
        new_dir.stat().st_gid,
        str(data),
        (new_dir / "data.txt").read_text(encoding="utf-8"),
    ) == (*expected_modes, old_dir.stat().st_gid, old_dir.stat().st_gid, str(new_dir), "cached")


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


@pytest.mark.skipif(os.name != "posix", reason="POSIX private migration")
def test_cache_dir_migration_fallback_on_migration_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    old_dir = str(tmp_path / "old-data")
    new_dir = str(tmp_path / "new-cache")
    os.makedirs(old_dir)

    monkeypatch.setattr("virtualenv.app_data.cache_migration.user_cache_dir", lambda **_kw: new_dir)
    monkeypatch.setattr("virtualenv.app_data.cache_migration.user_data_dir", lambda **_kw: old_dir)

    def broken_rename(_src: str, _dst: str) -> None:
        raise OSError(EXDEV, "cross-device")

    def broken_copy(_src: str, _dst: str, **_kwargs: bool) -> None:
        raise PermissionError(EACCES, "permission denied")

    monkeypatch.setattr("virtualenv.app_data.cache_migration.os.rename", broken_rename)
    monkeypatch.setattr("virtualenv.app_data.cache_migration.shutil.copytree", broken_copy)

    result = str(make_app_data(None, read_only=False, env={}))
    assert (result, os.path.isdir(old_dir), os.path.exists(new_dir)) == (old_dir, True, False)


@pytest.mark.skipif(os.name != "nt", reason="Windows move fallback")
def test_cache_dir_migration_windows_move_error(tmp_path: Path, mocker: MockerFixture) -> None:
    old_dir = tmp_path / "old-data"
    old_dir.mkdir()
    new_dir = tmp_path / "new-cache"
    mocker.patch("virtualenv.app_data.cache_migration.user_cache_dir", autospec=True, return_value=str(new_dir))
    mocker.patch("virtualenv.app_data.cache_migration.user_data_dir", autospec=True, return_value=str(old_dir))
    mocker.patch("virtualenv.app_data.cache_migration.shutil.move", autospec=True, side_effect=PermissionError)

    assert (str(make_app_data(None, read_only=False, env={})), old_dir.exists(), new_dir.exists()) == (
        str(old_dir),
        True,
        False,
    )


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
    old_dir: Final[Path] = tmp_path / "data"
    old_dir.mkdir()
    (old_dir / "test.txt").write_text("hello", encoding="utf-8")
    new_dir: Final[Path] = tmp_path / new_dir_rel
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

    assert {entry.name for entry in nested_cache_dirs[0].iterdir()} - {".virtualenv-migration.lock"} == {"Cache"}


@pytest.mark.parametrize(
    "cache_path",
    [pytest.param("cache", id="sibling"), pytest.param("data/Cache", id="nested")],
)
def test_cache_migration_preserves_config(tmp_path: Path, mocker: MockerFixture, cache_path: str) -> None:
    old_dir: Final[Path] = tmp_path / "data"
    old_dir.mkdir()
    (old_dir / "virtualenv.ini").write_text("[virtualenv]\nno_periodic_update = true\n", encoding="utf-8")
    (old_dir / "wheel").mkdir()
    (old_dir / "wheel/pip.whl").write_text("cached", encoding="utf-8")
    new_dir: Final[Path] = tmp_path / cache_path
    mocker.patch("virtualenv.app_data.cache_migration.user_cache_dir", autospec=True, return_value=str(new_dir))
    mocker.patch("virtualenv.app_data.cache_migration.user_data_dir", autospec=True, return_value=str(old_dir))

    assert (
        str(make_app_data(None, read_only=False, env={})),
        (new_dir / "wheel/pip.whl").read_text(encoding="utf-8"),
        (old_dir / "virtualenv.ini").read_text(encoding="utf-8"),
    ) == (str(new_dir), "cached", "[virtualenv]\nno_periodic_update = true\n")


@pytest.mark.parametrize("cache_path", [pytest.param("cache", id="sibling"), pytest.param("data/Cache", id="nested")])
def test_config_cache_migration_keeps_other_files(tmp_path: Path, mocker: MockerFixture, cache_path: str) -> None:
    old_dir = tmp_path / "data"
    old_dir.mkdir()
    (old_dir / "virtualenv.ini").touch()
    (old_dir / "work.ini").write_text("[work]\n", encoding="utf-8")
    (old_dir / "wheel").mkdir()
    (old_dir / "wheel/pip.whl").write_bytes(b"wheel")
    new_dir = tmp_path / cache_path
    mocker.patch("virtualenv.app_data.cache_migration.user_cache_dir", autospec=True, return_value=str(new_dir))
    mocker.patch("virtualenv.app_data.cache_migration.user_data_dir", autospec=True, return_value=str(old_dir))

    app_data = make_app_data(None, read_only=False, env={})
    migrated = (new_dir / "wheel/pip.whl").read_bytes()
    app_data.reset()

    assert (
        (old_dir / "work.ini").read_text(encoding="utf-8"),
        (old_dir / "virtualenv.ini").exists(),
        migrated,
        (new_dir / "work.ini").exists(),
    ) == ("[work]\n", True, b"wheel", False)


@pytest.mark.skipif(os.name != "posix", reason="POSIX group permissions")
def test_sibling_cache_migration_preserves_shared_group(tmp_path: Path, mocker: MockerFixture) -> None:
    old_dir: Final[Path] = tmp_path / "data"
    old_dir.mkdir()
    old_dir.chmod(0o2775)
    (old_dir / "virtualenv.ini").touch()
    (old_dir / "wheel").mkdir()
    new_dir: Final[Path] = tmp_path / "cache"
    mocker.patch("virtualenv.app_data.cache_migration.user_cache_dir", autospec=True, return_value=str(new_dir))
    mocker.patch("virtualenv.app_data.cache_migration.user_data_dir", autospec=True, return_value=str(old_dir))

    make_app_data(None, read_only=False, env={})

    assert (new_dir.stat().st_mode & 0o7777, new_dir.stat().st_gid) == (0o2770, old_dir.stat().st_gid)


def test_failed_config_cache_migration_reset_keeps_config(
    nested_cache_dirs: tuple[Path, Path], mocker: MockerFixture, caplog: pytest.LogCaptureFixture
) -> None:
    config: Final[Path] = nested_cache_dirs[0] / "virtualenv.ini"
    config.write_text("[virtualenv]\n", encoding="utf-8")
    (nested_cache_dirs[0] / "wheel").mkdir()
    (nested_cache_dirs[0] / "wheel/pip.whl").write_bytes(b"wheel")
    mocker.patch("virtualenv.app_data.cache_migration.shutil.move", autospec=True, side_effect=PermissionError)

    app_data: Final[AppData] = make_app_data(None, read_only=False, env={})
    try:
        app_data.reset()
        assert (
            app_data.transient,
            config.read_text(encoding="utf-8"),
            "move cache entries before removing" in caplog.text,
        ) == (True, "[virtualenv]\n", True)
    finally:
        app_data.close()


def test_cache_migration_resumes_into_existing_entries(tmp_path: Path, mocker: MockerFixture) -> None:
    old_dir: Final[Path] = tmp_path / "data"
    new_dir: Final[Path] = tmp_path / "cache"
    old_house: Final[Path] = old_dir / "wheel/house"
    new_house: Final[Path] = new_dir / "wheel/house"
    old_house.mkdir(parents=True)
    new_house.mkdir(parents=True)
    (old_dir / "virtualenv.ini").write_text("[virtualenv]\n", encoding="utf-8")
    (old_dir / ".virtualenv-migration-incomplete").touch()
    (old_house / "old.whl").write_bytes(b"old")
    (new_house / "new.whl").write_bytes(b"new")
    (old_house / "shared.whl").write_bytes(b"complete wheel")
    (new_house / "shared.whl").write_bytes(b"partial wheel")
    mocker.patch("virtualenv.app_data.cache_migration.user_cache_dir", autospec=True, return_value=str(new_dir))
    mocker.patch("virtualenv.app_data.cache_migration.user_data_dir", autospec=True, return_value=str(old_dir))

    app_data: Final[AppData] = make_app_data(None, read_only=False, env={})

    assert (
        str(app_data),
        sorted(path.name for path in new_house.iterdir()),
        (new_house / "shared.whl").read_bytes(),
        (old_dir / "virtualenv.ini").read_text(encoding="utf-8"),
        (old_dir / ".virtualenv-migration-incomplete").exists(),
    ) == (str(new_dir), ["new.whl", "old.whl", "shared.whl"], b"complete wheel", "[virtualenv]\n", False)


def test_read_only_cache_migration_uses_legacy_dir_on_lock_error(tmp_path: Path, mocker: MockerFixture) -> None:
    old_dir: Final[Path] = tmp_path / "data"
    new_dir: Final[Path] = tmp_path / "cache"
    old_dir.mkdir()
    (old_dir / "virtualenv.ini").touch()
    (old_dir / "wheel").mkdir()
    mocker.patch("virtualenv.app_data.cache_migration.user_cache_dir", autospec=True, return_value=str(new_dir))
    mocker.patch("virtualenv.app_data.cache_migration.user_data_dir", autospec=True, return_value=str(old_dir))
    mocker.patch(
        "virtualenv.app_data.cache_migration.ReentrantFileLock.lock_for_key", autospec=True, side_effect=PermissionError
    )

    assert (str(make_app_data(None, read_only=True, env={})), new_dir.exists()) == (str(old_dir), False)


@pytest.mark.skipif(not fs_supports_symlink(), reason="symlinks are unavailable")
def test_config_cache_migration_leaves_linked_data_dir(tmp_path: Path, mocker: MockerFixture) -> None:
    target: Final[Path] = tmp_path / "target"
    target.mkdir()
    (target / "virtualenv.ini").write_text("[virtualenv]\n", encoding="utf-8")
    (target / "work.ini").write_text("[work]\n", encoding="utf-8")
    (target / "wheel").mkdir()
    (target / "wheel/pip.whl").write_text("cached", encoding="utf-8")
    old_dir: Final[Path] = tmp_path / "data"
    old_dir.symlink_to(target, target_is_directory=True)
    new_dir: Final[Path] = tmp_path / "cache"
    mocker.patch("virtualenv.app_data.cache_migration.user_cache_dir", autospec=True, return_value=str(new_dir))
    mocker.patch("virtualenv.app_data.cache_migration.user_data_dir", autospec=True, return_value=str(old_dir))

    app_data: Final[AppData] = make_app_data(None, read_only=False, env={})

    assert (
        str(app_data),
        old_dir.is_symlink(),
        sorted(path.name for path in target.iterdir()),
        (new_dir / "wheel/pip.whl").read_text(encoding="utf-8"),
        (new_dir / "virtualenv.ini").exists(),
        (new_dir / "work.ini").exists(),
    ) == (str(new_dir), True, ["virtualenv.ini", "wheel", "work.ini"], "cached", False, False)


@pytest.mark.skipif(not fs_supports_symlink(), reason="symlinks are unavailable")
def test_interrupted_linked_migration_retries_before_first_copy(tmp_path: Path, mocker: MockerFixture) -> None:
    old_dir = tmp_path / "data"
    target = tmp_path / "target"
    target.mkdir()
    (target / "virtualenv.ini").touch()
    (target / "wheel").mkdir()
    (target / "wheel/pip.whl").write_bytes(b"cached")
    old_dir.symlink_to(target, target_is_directory=True)
    new_dir = tmp_path / "cache"
    mocker.patch("virtualenv.app_data.cache_migration.user_data_dir", autospec=True, return_value=str(old_dir))
    mocker.patch("virtualenv.app_data.cache_migration.user_cache_dir", autospec=True, return_value=str(new_dir))
    rename = os.rename

    def interrupt_after_rename(source: str, dest: str) -> None:
        rename(source, dest)
        raise KeyboardInterrupt

    interrupted = mocker.patch("os.rename", autospec=True, side_effect=interrupt_after_rename)
    with pytest.raises(KeyboardInterrupt):
        cache_dir_with_migration(read_only=False)
    mocker.stop(interrupted)
    assert (cache_dir_with_migration(read_only=False), (new_dir / "wheel/pip.whl").read_bytes()) == (
        str(new_dir),
        b"cached",
    )


@pytest.mark.skipif(not fs_supports_symlink(), reason="symlinks are unavailable")
def test_linked_migration_warning_names_copy_marker(
    tmp_path: Path, mocker: MockerFixture, caplog: pytest.LogCaptureFixture
) -> None:
    target = tmp_path / "target"
    target.mkdir()
    (target / "virtualenv.ini").touch()
    (target / "wheel").mkdir()
    (target / "wheel/pip.whl").touch()
    old_dir = tmp_path / "data"
    old_dir.symlink_to(target, target_is_directory=True)
    new_dir = tmp_path / "cache"
    mocker.patch("virtualenv.app_data.cache_migration.user_data_dir", autospec=True, return_value=str(old_dir))
    mocker.patch("virtualenv.app_data.cache_migration.user_cache_dir", autospec=True, return_value=str(new_dir))
    mocker.patch("virtualenv.app_data.cache_migration.shutil.copy2", autospec=True, side_effect=PermissionError)
    marker = new_dir / ".virtualenv-migration-incomplete"

    assert (
        cache_dir_with_migration(read_only=False),
        marker.exists(),
        f"copy cache entries before removing {marker}" in caplog.text,
    ) == (None, True, True)


@pytest.mark.skipif(not fs_supports_symlink(), reason="symlinks are unavailable")
def test_linked_cache_migration_replaces_target_link(tmp_path: Path, mocker: MockerFixture) -> None:
    target: Final[Path] = tmp_path / "target"
    target.mkdir()
    (target / "virtualenv.ini").touch()
    (target / "wheel").mkdir()
    (target / "wheel/pip.whl").write_text("cached", encoding="utf-8")
    old_dir: Final[Path] = tmp_path / "data"
    old_dir.symlink_to(target, target_is_directory=True)
    new_dir: Final[Path] = tmp_path / "cache"
    new_dir.mkdir()
    (new_dir / ".virtualenv-migration-incomplete").touch()
    outside: Final[Path] = tmp_path / "outside"
    outside.mkdir()
    (outside / "pip.whl").write_text("keep", encoding="utf-8")
    (new_dir / "wheel").symlink_to(outside, target_is_directory=True)
    mocker.patch("virtualenv.app_data.cache_migration.user_cache_dir", autospec=True, return_value=str(new_dir))
    mocker.patch("virtualenv.app_data.cache_migration.user_data_dir", autospec=True, return_value=str(old_dir))

    make_app_data(None, read_only=False, env={})

    assert (
        (outside / "pip.whl").read_text(encoding="utf-8"),
        (new_dir / "wheel/pip.whl").read_text(encoding="utf-8"),
    ) == (
        "keep",
        "cached",
    )


@pytest.mark.parametrize(
    ("rollback_error", "cleanup_error", "retry_index"),
    [
        pytest.param(None, None, 1, id="rollback-succeeds"),
        pytest.param(OSError("permission denied"), None, 1, id="rollback-fails"),
        pytest.param(None, OSError("permission denied"), 1, id="cleanup-fails"),
    ],
)
def test_cache_dir_nested_migration_failure_selection(
    nested_cache_dirs: tuple[Path, Path],
    mocker: MockerFixture,
    rollback_error: OSError | None,
    cleanup_error: OSError | None,
    retry_index: int,
) -> None:
    old_dir: Final[Path] = nested_cache_dirs[0]
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


def test_cache_dir_interrupted_migration_resumes(nested_cache_dirs: tuple[Path, Path], mocker: MockerFixture) -> None:
    move = shutil.move
    calls = 0

    def interrupt_after_one_move(source: str, target: str) -> str:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise KeyboardInterrupt
        return move(source, target)

    mocker.patch("virtualenv.app_data.cache_migration.shutil.move", autospec=True, side_effect=interrupt_after_one_move)

    with pytest.raises(KeyboardInterrupt):
        make_app_data(None, read_only=False, env={})

    assert (
        str(make_app_data(None, read_only=False, env={})),
        sorted(entry.name for entry in nested_cache_dirs[1].iterdir()),
    ) == (str(nested_cache_dirs[1]), ["one.txt", "two.txt"])


@pytest.mark.skipif(os.name != "posix" or not fs_supports_symlink(), reason="POSIX symlinks and modes")
def test_linked_cache_migration_keeps_safe_shared_target(tmp_path: Path, mocker: MockerFixture) -> None:
    target = tmp_path / "target"
    target.mkdir()
    (target / "virtualenv.ini").touch()
    (target / "wheel").mkdir()
    (target / "wheel/pip.whl").write_text("cached", encoding="utf-8")
    old_dir = tmp_path / "data"
    old_dir.symlink_to(target, target_is_directory=True)
    new_dir = tmp_path / "cache"
    new_dir.mkdir()
    new_dir.chmod(0o2770)
    (new_dir / ".virtualenv-migration-incomplete").touch()
    mocker.patch("virtualenv.app_data.cache_migration.user_cache_dir", autospec=True, return_value=str(new_dir))
    mocker.patch("virtualenv.app_data.cache_migration.user_data_dir", autospec=True, return_value=str(old_dir))
    chmod = os.chmod

    def reject_target(path: str, mode: int, **kwargs: bool) -> None:
        if path == str(new_dir):
            raise PermissionError
        chmod(path, mode, **kwargs)

    mocker.patch("virtualenv.app_data.cache_migration.os.chmod", autospec=True, side_effect=reject_target)

    make_app_data(None, read_only=False, env={})

    assert (new_dir.stat().st_mode & 0o7777, (new_dir / "wheel/pip.whl").read_text(encoding="utf-8")) == (
        0o2770,
        "cached",
    )


def test_cache_dir_concurrent_nested_migration_waits(
    nested_cache_dirs: tuple[Path, Path], mocker: MockerFixture
) -> None:
    move = shutil.move
    results: list[str | None] = []
    racers: list[threading.Thread] = []

    def start_racer_once(source: str, target: str) -> str:
        if not racers:
            racers.append(threading.Thread(target=lambda: results.append(cache_dir_with_migration(read_only=False))))
            racers[0].start()
            racers[0].join(0.5)
        return move(source, target)

    mocker.patch("virtualenv.app_data.cache_migration.shutil.move", autospec=True, side_effect=start_racer_once)

    first: Final[str | None] = cache_dir_with_migration(read_only=False)
    racers[0].join()

    assert (first, results, sorted(entry.name for entry in nested_cache_dirs[1].iterdir())) == (
        str(nested_cache_dirs[1]),
        [str(nested_cache_dirs[1])],
        ["one.txt", "two.txt"],
    )


@pytest.mark.skipif(os.name != "posix", reason="POSIX cross-device migration")
def test_concurrent_sibling_migration_locks_out_second_copy(tmp_path: Path, mocker: MockerFixture) -> None:
    old_dir = tmp_path / "data"
    old_dir.mkdir()
    (old_dir / "entry").write_bytes(b"legacy")
    new_dir = tmp_path / "cache"
    mocker.patch("virtualenv.app_data.cache_migration.user_data_dir", autospec=True, return_value=str(old_dir))
    mocker.patch("virtualenv.app_data.cache_migration.user_cache_dir", autospec=True, return_value=str(new_dir))
    _fail_cross_device_rename(mocker, old_dir)
    copytree = shutil.copytree

    def copy_with_lock(source: str, target: str, **kwargs: bool) -> str:
        with pytest.raises(Timeout):
            FileLock(tmp_path / ".virtualenv-migration.lock", timeout=0).acquire()
        return copytree(source, target, **kwargs)

    mocker.patch("virtualenv.app_data.cache_migration.shutil.copytree", autospec=True, side_effect=copy_with_lock)
    assert (cache_dir_with_migration(read_only=False), (new_dir / "entry").read_bytes(), old_dir.exists()) == (
        str(new_dir),
        b"legacy",
        False,
    )


def _fail_cross_device_rename(mocker: MockerFixture, old_dir: Path) -> None:
    rename = os.rename

    def cross_device(source: str, target: str) -> None:
        if source == str(old_dir):
            raise OSError(EXDEV, "cross-device")
        rename(source, target)

    mocker.patch("virtualenv.app_data.cache_migration.os.rename", autospec=True, side_effect=cross_device)


@pytest.mark.skipif(os.name != "posix", reason="POSIX group permissions")
def test_shared_migration_keeps_concurrently_created_parent(tmp_path: Path, mocker: MockerFixture) -> None:
    old_dir = tmp_path / "data"
    old_dir.mkdir()
    old_dir.chmod(0o2770)
    parent = tmp_path / "new"
    new_dir = parent / "cache"
    mocker.patch("virtualenv.app_data.cache_migration.user_data_dir", autospec=True, return_value=str(old_dir))
    mocker.patch("virtualenv.app_data.cache_migration.user_cache_dir", autospec=True, return_value=str(new_dir))
    mkdir = os.mkdir

    def create_concurrently(path: str, mode: int, *, dir_fd: int | None = None) -> None:
        if path == str(parent):
            mkdir(path, 0o700)
            parent.chmod(0o750)
        mkdir(path, mode, dir_fd=dir_fd)

    mocker.patch("virtualenv.app_data.cache_migration.os.mkdir", autospec=True, side_effect=create_concurrently)
    assert (cache_dir_with_migration(read_only=False), parent.stat().st_mode & 0o777, old_dir.exists()) == (
        str(new_dir),
        0o750,
        False,
    )


def test_cache_dir_incomplete_migration_keeps_old_on_retry_failure(
    nested_cache_dirs: tuple[Path, Path], mocker: MockerFixture
) -> None:
    old_dir, new_dir = nested_cache_dirs
    new_dir.mkdir()
    (old_dir / ".virtualenv-migration-incomplete").touch()
    mocker.patch("virtualenv.app_data.cache_migration.shutil.move", autospec=True, side_effect=PermissionError)

    assert (str(make_app_data(None, read_only=False, env={})), (old_dir / "one.txt").exists()) == (
        str(old_dir),
        True,
    )


def test_cache_dir_existing_nested_cache_stays_selected(nested_cache_dirs: tuple[Path, Path]) -> None:
    new_dir: Final[Path] = nested_cache_dirs[1]
    new_dir.mkdir()

    assert str(make_app_data(None, read_only=False, env={})) == str(new_dir)


@pytest.fixture
def nested_cache_dirs(tmp_path: Path, mocker: MockerFixture) -> tuple[Path, Path]:
    old_dir: Final[Path] = tmp_path / "data"
    old_dir.mkdir()
    (old_dir / "one.txt").write_text("one", encoding="utf-8")
    (old_dir / "two.txt").write_text("two", encoding="utf-8")
    new_dir: Final[Path] = old_dir / "Cache"
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


@pytest.mark.parametrize("operation", ["shutil.copyfileobj", "os.fsync"])
def test_zipapp_extract_keeps_previous_file_on_write_error(
    fake_zipapp_root: Path, tmp_path: Path, mocker: MockerFixture, operation: str
) -> None:
    dest: Final[Path] = tmp_path / "extracted.txt"
    dest.write_text("previous", encoding="utf-8")
    mocker.patch(operation, autospec=True, side_effect=OSError(EACCES, "write failed"))

    with pytest.raises(OSError, match="write failed"):
        zipapp.extract(fake_zipapp_root / "virtualenv" / "payload.txt", dest)

    assert (dest.read_text(encoding="utf-8"), set(tmp_path.iterdir())) == ("previous", {dest, fake_zipapp_root})


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
    [
        pytest.param(0o2775, 0o2770, id="group-write"),
        pytest.param(0o2777, 0o2770, id="other-write"),
        pytest.param(0o2755, 0o2750, id="group-read"),
    ],
)
def test_app_data_setgid_keeps_group_write(app_data_default: Path, mode: int, expected: int) -> None:
    app_data_default.mkdir()
    app_data_default.chmod(mode)
    make_app_data(None, read_only=False, env={})
    assert app_data_default.stat().st_mode & 0o7777 == expected


@pytest.mark.skipif(os.name != "posix" or os.geteuid() == 0, reason="non-root cache owner")
def test_app_data_rejects_non_owned_cache(
    app_data_default: Path, mocker: MockerFixture, caplog: pytest.LogCaptureFixture
) -> None:
    app_data_default.mkdir()
    app_data_default.chmod(0o1777)
    mocker.patch("virtualenv.app_data.os.geteuid", autospec=True, return_value=app_data_default.stat().st_uid + 1)
    data: Final[AppData] = make_app_data(None, read_only=False, env={})
    try:
        assert (
            data.transient,
            app_data_default.stat().st_mode & 0o7777,
            "owned by uid" in caplog.text,
        ) == (True, 0o1777, True)
    finally:
        data.close()


@pytest.mark.skipif(os.name != "posix", reason="POSIX ownership")
@pytest.mark.parametrize("read_only", [False, True])
def test_app_data_keeps_root_owned_cache(app_data_default: Path, mocker: MockerFixture, read_only: bool) -> None:
    app_data_default.mkdir()
    app_data_default.chmod(0o755)
    original_stat = os.stat

    def root_owned(
        path: str | int | Path, *, dir_fd: int | None = None, follow_symlinks: bool = True
    ) -> os.stat_result:
        info = original_stat(path, dir_fd=dir_fd, follow_symlinks=follow_symlinks)
        if path == str(app_data_default):
            return os.stat_result((*info[:ST_UID], 0, *info[ST_UID + 1 :]))
        return info

    mocker.patch("virtualenv.app_data.os.geteuid", autospec=True, return_value=1)
    mocker.patch("virtualenv.app_data.os.stat", autospec=True, side_effect=root_owned)
    data = make_app_data(None, read_only=read_only, env={})

    assert (str(data), data.transient, app_data_default.stat().st_mode & 0o777) == (str(app_data_default), False, 0o755)


@pytest.mark.skipif(os.name != "posix" or os.geteuid() == 0, reason="non-root cache owner")
def test_read_only_default_rejects_foreign_cache(app_data_default: Path, mocker: MockerFixture) -> None:
    app_data_default.mkdir()
    mocker.patch("virtualenv.app_data.os.geteuid", autospec=True, return_value=app_data_default.stat().st_uid + 1)
    with pytest.raises(RuntimeError, match="explicit cache path"):
        make_app_data(None, read_only=True, env={})
    assert str(make_app_data(str(app_data_default), read_only=True, env={})) == str(app_data_default)


@pytest.mark.skipif(os.name != "posix", reason="POSIX directory permission bits")
def test_migrated_cache_closes_writable_descendants(tmp_path: Path, mocker: MockerFixture) -> None:
    old_dir = tmp_path / "private" / "virtualenv"
    wheel_dir = old_dir / "wheel"
    wheel_dir.mkdir(parents=True)
    old_dir.chmod(0o775)
    wheel_dir.chmod(0o775)
    old_dir.parent.chmod(0o700)
    (old_dir / "wheel.txt").write_text("cached", encoding="utf-8")
    new_dir = tmp_path / "cache" / "virtualenv"
    new_dir.parent.mkdir(mode=0o755)
    mocker.patch("virtualenv.app_data.cache_migration.user_cache_dir", autospec=True, return_value=str(new_dir))
    mocker.patch("virtualenv.app_data.cache_migration.user_data_dir", autospec=True, return_value=str(old_dir))

    app_data = make_app_data(None, read_only=False, env={})

    assert (
        str(app_data),
        new_dir.stat().st_mode & 0o7777,
        (new_dir / "wheel").stat().st_mode & 0o7777,
        old_dir.exists(),
    ) == (str(new_dir), 0o700, 0o775, False)


@pytest.mark.skipif(os.name != "posix", reason="POSIX directory permission bits")
@pytest.mark.parametrize(("old_mode", "expected"), [(0o755, 0o700), (0o2775, 0o2770)])
def test_config_migration_closes_cache_before_move(
    tmp_path: Path, mocker: MockerFixture, old_mode: int, expected: int
) -> None:
    old_dir = tmp_path / "private" / "virtualenv"
    wheel_dir = old_dir / "wheel"
    wheel_dir.mkdir(parents=True)
    old_dir.parent.chmod(0o700)
    old_dir.chmod(old_mode)
    wheel_dir.chmod(0o775)
    (old_dir / "virtualenv.ini").touch()
    new_dir = tmp_path / "cache" / "virtualenv"
    new_dir.parent.mkdir(mode=0o755)
    mocker.patch("virtualenv.app_data.cache_migration.user_cache_dir", autospec=True, return_value=str(new_dir))
    mocker.patch("virtualenv.app_data.cache_migration.user_data_dir", autospec=True, return_value=str(old_dir))
    move = shutil.move

    def check_mode(source: str, target: str) -> str:
        assert new_dir.stat().st_mode & 0o7777 == expected
        return move(source, target)

    mocker.patch("virtualenv.app_data.cache_migration.shutil.move", autospec=True, side_effect=check_mode)

    make_app_data(None, read_only=False, env={})

    assert (new_dir.stat().st_mode & 0o7777, wheel_dir.exists(), (old_dir / "virtualenv.ini").exists()) == (
        expected,
        False,
        True,
    )


@pytest.mark.skipif(os.name != "posix", reason="POSIX directory permission bits")
@pytest.mark.parametrize(("old_mode", "expected"), [(0o755, 0o700), (0o2775, 0o2770)])
@pytest.mark.parametrize("read_only", [False, True])
def test_nested_migration_retry_closes_cache_before_move(
    tmp_path: Path, mocker: MockerFixture, old_mode: int, expected: int, read_only: bool
) -> None:
    old_dir = tmp_path / "private" / "virtualenv"
    wheel_dir = old_dir / "wheel"
    wheel_dir.mkdir(parents=True)
    old_dir.parent.chmod(0o700)
    old_dir.chmod(old_mode)
    (old_dir / "virtualenv.ini").touch()
    (wheel_dir / "pip.whl").write_bytes(b"wheel")
    new_dir = old_dir / "Cache"
    new_dir.mkdir(mode=0o755)
    (old_dir / ".virtualenv-migration-incomplete").touch()
    mocker.patch("virtualenv.app_data.cache_migration.user_cache_dir", autospec=True, return_value=str(new_dir))
    mocker.patch("virtualenv.app_data.cache_migration.user_data_dir", autospec=True, return_value=str(old_dir))
    move = shutil.move

    def check_mode(source: str, target: str) -> str:
        assert new_dir.stat().st_mode & 0o7777 == expected
        return move(source, target)

    mocker.patch("virtualenv.app_data.cache_migration.shutil.move", autospec=True, side_effect=check_mode)

    make_app_data(None, read_only=read_only, env={})

    assert (new_dir.stat().st_mode & 0o7777, (new_dir / "wheel/pip.whl").read_bytes()) == (expected, b"wheel")


@pytest.mark.skipif(os.name != "posix", reason="POSIX directory permission bits")
@pytest.mark.parametrize(("source_mode", "expected"), [(0o755, 0o700), (0o2775, 0o2770)])
def test_linked_config_retry_closes_cache_before_copy(
    tmp_path: Path, mocker: MockerFixture, source_mode: int, expected: int
) -> None:
    source = tmp_path / "private" / "virtualenv"
    wheel_dir = source / "wheel"
    wheel_dir.mkdir(parents=True)
    source.parent.chmod(0o700)
    source.chmod(source_mode)
    (source / "virtualenv.ini").touch()
    (wheel_dir / "pip.whl").write_bytes(b"wheel")
    old_dir = tmp_path / "legacy"
    old_dir.symlink_to(source, target_is_directory=True)
    new_dir = tmp_path / "cache" / "virtualenv"
    new_dir.mkdir(parents=True, mode=0o755)
    (new_dir / ".virtualenv-migration-incomplete").touch()
    mocker.patch("virtualenv.app_data.cache_migration.user_cache_dir", autospec=True, return_value=str(new_dir))
    mocker.patch("virtualenv.app_data.cache_migration.user_data_dir", autospec=True, return_value=str(old_dir))
    copy2 = shutil.copy2

    def check_mode(source_path: str, target_path: str) -> str:
        assert new_dir.stat().st_mode & 0o7777 == expected
        return copy2(source_path, target_path)

    mocker.patch("virtualenv.app_data.cache_migration.shutil.copy2", autospec=True, side_effect=check_mode)

    make_app_data(None, read_only=False, env={})

    assert (new_dir.stat().st_mode & 0o7777, (new_dir / "wheel/pip.whl").read_bytes()) == (expected, b"wheel")


@pytest.mark.skipif(os.name != "posix", reason="POSIX directory permission bits")
@pytest.mark.parametrize(("source_mode", "expected"), [(0o755, 0o700), (0o2775, 0o2770)])
@pytest.mark.parametrize("read_only", [False, True])
def test_linked_migration_closes_target_before_move(
    tmp_path: Path, mocker: MockerFixture, source_mode: int, expected: int, read_only: bool
) -> None:
    target = tmp_path / "private" / "virtualenv"
    target.mkdir(parents=True)
    target.parent.chmod(0o700)
    target.chmod(source_mode)
    (target / "wheel.txt").write_bytes(b"wheel")
    old_dir = tmp_path / "legacy"
    old_dir.symlink_to(target, target_is_directory=True)
    new_dir = tmp_path / "cache" / "virtualenv"
    new_dir.parent.mkdir(mode=0o755)
    mocker.patch("virtualenv.app_data.cache_migration.user_cache_dir", autospec=True, return_value=str(new_dir))
    mocker.patch("virtualenv.app_data.cache_migration.user_data_dir", autospec=True, return_value=str(old_dir))
    move = shutil.move

    def check_mode(source: str, destination: str) -> str:
        assert target.stat().st_mode & 0o7777 == expected
        return move(source, destination)

    mocker.patch("virtualenv.app_data.cache_migration.shutil.move", autospec=True, side_effect=check_mode)

    make_app_data(None, read_only=read_only, env={})

    assert (new_dir.is_symlink(), target.stat().st_mode & 0o7777) == (True, expected)


@pytest.mark.skipif(os.name != "posix", reason="POSIX directory permission bits")
def test_cross_device_cache_copy_keeps_target_private_during_copy(tmp_path: Path, mocker: MockerFixture) -> None:
    old_dir = tmp_path / "private" / "virtualenv"
    old_dir.mkdir(parents=True)
    old_dir.chmod(0o700)
    (old_dir / "wheel.txt").write_text("cached", encoding="utf-8")
    new_dir = tmp_path / "cache" / "virtualenv"
    new_dir.parent.mkdir(mode=0o755)
    mocker.patch("virtualenv.app_data.cache_migration.user_cache_dir", autospec=True, return_value=str(new_dir))
    mocker.patch("virtualenv.app_data.cache_migration.user_data_dir", autospec=True, return_value=str(old_dir))
    _fail_cross_device_rename(mocker, old_dir)
    copytree = shutil.copytree

    def check_target_mode(source: str, target: str, **kwargs: bool) -> str:
        assert (Path(target).stat().st_mode & 0o777, new_dir.exists()) == (0o700, False)
        return copytree(source, target, **kwargs)

    mocker.patch("virtualenv.app_data.cache_migration.shutil.copytree", autospec=True, side_effect=check_target_mode)

    assert (
        str(make_app_data(None, read_only=False, env={})),
        (new_dir / "wheel.txt").read_text(encoding="utf-8"),
        new_dir.stat().st_mode & 0o777,
        old_dir.exists(),
    ) == (str(new_dir), "cached", 0o700, False)


@pytest.mark.skipif(os.name != "posix", reason="POSIX group permissions")
def test_legacy_cache_migration_preserves_setgid_group(tmp_path: Path, mocker: MockerFixture) -> None:
    old_dir = tmp_path / "data"
    old_dir.mkdir()
    old_dir.chmod(0o2775)
    old_gid = old_dir.stat().st_gid
    (old_dir / "wheel.txt").touch()
    new_dir = tmp_path / "cache"
    mocker.patch("virtualenv.app_data.cache_migration.user_cache_dir", autospec=True, return_value=str(new_dir))
    mocker.patch("virtualenv.app_data.cache_migration.user_data_dir", autospec=True, return_value=str(old_dir))

    make_app_data(None, read_only=False, env={})

    assert (new_dir.stat().st_mode & 0o7777, new_dir.stat().st_gid) == (0o2770, old_gid)


@pytest.mark.skipif(os.name != "posix" or not (set(os.getgroups()) - {os.getgid()}), reason="POSIX second group")
def test_cross_device_shared_cache_keeps_group_during_copy(tmp_path: Path, mocker: MockerFixture) -> None:
    old_dir = tmp_path / "data"
    old_dir.mkdir()
    old_dir.chmod(0o2775)
    (old_dir / "wheel.txt").write_text("cached", encoding="utf-8")
    new_dir = tmp_path / "cache" / "virtualenv"
    new_dir.parent.mkdir()
    os.chown(new_dir.parent, -1, (set(os.getgroups()) - {os.getgid()}).pop())
    new_dir.parent.chmod(0o2770)
    mocker.patch("virtualenv.app_data.cache_migration.user_cache_dir", autospec=True, return_value=str(new_dir))
    mocker.patch("virtualenv.app_data.cache_migration.user_data_dir", autospec=True, return_value=str(old_dir))
    _fail_cross_device_rename(mocker, old_dir)
    copytree = shutil.copytree

    def check_group(source: str, target: str, **kwargs: bool) -> str:
        assert Path(target).stat().st_gid == Path(source).stat().st_gid
        return copytree(source, target, **kwargs)

    mocker.patch("virtualenv.app_data.cache_migration.shutil.copytree", autospec=True, side_effect=check_group)

    make_app_data(None, read_only=False, env={})

    assert (new_dir.stat().st_mode & 0o7777, (new_dir / "wheel.txt").read_text(encoding="utf-8")) == (
        0o2770,
        "cached",
    )


@pytest.mark.skipif(os.name != "posix" or not fs_supports_symlink(), reason="POSIX symlinks and modes")
def test_legacy_cache_migration_moves_link_and_closes_target(tmp_path: Path, mocker: MockerFixture) -> None:
    target = tmp_path / "target"
    target.mkdir()
    target.chmod(0o2775)
    old_dir = tmp_path / "data"
    old_dir.symlink_to(target, target_is_directory=True)
    new_dir = tmp_path / "cache"
    mocker.patch("virtualenv.app_data.cache_migration.user_cache_dir", autospec=True, return_value=str(new_dir))
    mocker.patch("virtualenv.app_data.cache_migration.user_data_dir", autospec=True, return_value=str(old_dir))

    assert (
        str(make_app_data(None, read_only=False, env={})),
        new_dir.is_symlink(),
        old_dir.exists(),
        target.stat().st_mode & 0o7777,
    ) == (str(target), True, False, 0o2770)


@pytest.mark.skipif(os.name != "posix", reason="POSIX rename across devices")
def test_cross_device_cache_copy_interrupted_retries(tmp_path: Path, mocker: MockerFixture) -> None:
    old_dir = tmp_path / "data" / "virtualenv"
    old_dir.mkdir(parents=True)
    (old_dir / "wheel.txt").write_text("cached", encoding="utf-8")
    new_dir = tmp_path / "cache" / "virtualenv"
    mocker.patch("virtualenv.app_data.cache_migration.user_cache_dir", autospec=True, return_value=str(new_dir))
    mocker.patch("virtualenv.app_data.cache_migration.user_data_dir", autospec=True, return_value=str(old_dir))
    _fail_cross_device_rename(mocker, old_dir)
    mocker.patch("virtualenv.app_data.cache_migration.shutil.copytree", autospec=True, side_effect=KeyboardInterrupt)
    with pytest.raises(KeyboardInterrupt):
        make_app_data(None, read_only=False, env={})
    assert not new_dir.exists()
    assert not list(new_dir.parent.glob(".virtualenv-migration-*"))
    mocker.stopall()
    mocker.patch("virtualenv.app_data.cache_migration.user_cache_dir", autospec=True, return_value=str(new_dir))
    mocker.patch("virtualenv.app_data.cache_migration.user_data_dir", autospec=True, return_value=str(old_dir))

    assert (str(make_app_data(None, read_only=False, env={})), (new_dir / "wheel.txt").read_text(encoding="utf-8")) == (
        str(new_dir),
        "cached",
    )
