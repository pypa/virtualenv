from __future__ import annotations

import concurrent.futures
import os
import sys
import traceback
import zipfile
from stat import S_IEXEC, S_IREAD, S_IRGRP, S_IRWXU, S_IWUSR
from typing import TYPE_CHECKING, Final

import pytest

from virtualenv.app_data import (
    AppDataDiskFolder,
    TempAppData,
    _cache_dir_with_migration,
    _default_app_data_dir,
    make_app_data,
)
from virtualenv.info import fs_supports_symlink
from virtualenv.util import zipapp
from virtualenv.util.lock import ReentrantFileLock
from virtualenv.util.path import copy, safe_delete, symlink
from virtualenv.util.subprocess import run_cmd

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from pytest_mock import MockerFixture


@pytest.mark.skipif(os.name != "posix", reason="POSIX directory permission bits")
@pytest.mark.parametrize("existing", [pytest.param(False, id="new"), pytest.param(True, id="existing")])
def test_app_data_default_permissions(app_data_default: Path, existing: bool) -> None:
    if existing:
        app_data_default.mkdir()
        app_data_default.chmod(0o777)
    previous: Final = os.umask(0)
    try:
        data: Final = make_app_data(None, read_only=False, env={})
    finally:
        os.umask(previous)
    assert (str(data), app_data_default.stat().st_mode & 0o777) == (str(app_data_default), 0o755 if existing else 0o700)


@pytest.mark.skipif(os.name != "posix", reason="POSIX directory permission bits")
@pytest.mark.parametrize("override", [pytest.param(False, id="argument"), pytest.param(True, id="environment")])
def test_app_data_explicit_permissions(tmp_path: Path, override: bool) -> None:
    tmp_path.chmod(0o775)
    data: Final = make_app_data(
        None if override else str(tmp_path),
        read_only=False,
        env={"VIRTUALENV_OVERRIDE_APP_DATA": str(tmp_path)} if override else {},
    )
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
    mocker.patch("virtualenv.app_data.os.chmod", autospec=True, side_effect=PermissionError)
    data: Final = make_app_data(None, read_only=False, env={})
    try:
        assert isinstance(data, TempAppData)
        assert str(data) != str(app_data_default)
    finally:
        data.close()


@pytest.mark.parametrize("writable", [pytest.param(False, id="unwritable"), pytest.param(True, id="writable")])
def test_app_data_explicit_create_failure(tmp_path: Path, mocker: MockerFixture, writable: bool) -> None:
    mocker.patch("virtualenv.app_data.os.makedirs", autospec=True, side_effect=PermissionError)
    mocker.patch("virtualenv.app_data.os.access", autospec=True, return_value=writable)
    data: Final = make_app_data(str(tmp_path), read_only=False, env={})
    try:
        assert (data.transient, str(data) == str(tmp_path)) == (not writable, writable)
    finally:
        data.close()


@pytest.fixture
def app_data_default(tmp_path: Path, mocker: MockerFixture) -> Path:
    folder: Final = tmp_path / "cache"
    mocker.patch("virtualenv.app_data.user_cache_dir", autospec=True, return_value=str(folder))
    mocker.patch("virtualenv.app_data.user_data_dir", autospec=True, return_value=str(tmp_path / "old"))
    return folder


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
def test_safe_delete_raises_the_original_error_not_a_retry_failure(tmp_path: Path) -> None:
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        pytest.skip("root bypasses the permission bits that make the delete fail")
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
def test_safe_delete_keeps_the_other_mode_bits_when_clearing_read_only(tmp_path: Path) -> None:
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        pytest.skip("root bypasses the permission bits that make the delete fail")
    target = tmp_path / "target"
    target.mkdir()
    blocked = target / "wheel.py"
    blocked.write_text("cached", encoding="utf-8")
    blocked.chmod(S_IREAD | S_IRGRP)
    target.chmod(S_IREAD | S_IEXEC)  # the unlink fails, so the mode the handler left behind stays observable

    try:
        with pytest.raises(PermissionError):
            safe_delete(target)
        assert blocked.stat().st_mode & 0o777 == S_IREAD | S_IRGRP | S_IWUSR
    finally:
        target.chmod(S_IRWXU)


@pytest.mark.skipif(not fs_supports_symlink(), reason="symlink is not supported")
@pytest.mark.parametrize("operation", [pytest.param(copy, id="copy"), pytest.param(symlink, id="symlink")])
@pytest.mark.parametrize("directory", [pytest.param(False, id="file"), pytest.param(True, id="directory")])
@pytest.mark.parametrize("loop", [pytest.param(False, id="missing-target"), pytest.param(True, id="self-loop")])
def test_replace_dangling_symlink(
    tmp_path: Path, operation: Callable[[Path, Path], None], directory: bool, loop: bool
) -> None:
    source: Final[Path] = tmp_path / "source"
    if directory:
        source.mkdir()
    (source / "file.txt" if directory else source).write_text("new", encoding="utf-8")
    destination: Final[Path] = tmp_path / "destination"
    outside: Final[Path] = tmp_path / "outside"
    destination.symlink_to(destination if loop else outside, target_is_directory=directory)

    operation(source, destination)

    assert (
        destination.is_symlink(),
        (destination / "file.txt" if directory else destination).read_text(encoding="utf-8"),
        destination.resolve(),
        outside.exists(),
    ) == (operation is symlink, "new", source.resolve() if operation is symlink else destination, False)


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
            except Exception:  # ruff:ignore[blind-except, try-except-in-loop]
                pytest.fail(traceback.format_exc())


class TestDefaultAppDataDir:
    def test_override_env_var(self, tmp_path: Path) -> None:
        custom = str(tmp_path / "custom")
        env = {"VIRTUALENV_OVERRIDE_APP_DATA": custom}
        assert _default_app_data_dir(env) == custom

    def test_no_override_returns_cache_dir(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("VIRTUALENV_OVERRIDE_APP_DATA", raising=False)
        result = _default_app_data_dir(os.environ)
        assert result


class TestCacheDirMigration:
    def test_migrate_old_to_new(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        old_dir = str(tmp_path / "old-data")
        new_dir = str(tmp_path / "new-cache")
        os.makedirs(old_dir)
        (tmp_path / "old-data" / "test.txt").write_text("hello", encoding="utf-8")

        monkeypatch.setattr("virtualenv.app_data.user_cache_dir", lambda **_kw: new_dir)
        monkeypatch.setattr("virtualenv.app_data.user_data_dir", lambda **_kw: old_dir)

        result = _cache_dir_with_migration()
        assert result == new_dir
        assert os.path.isdir(new_dir)
        assert not os.path.isdir(old_dir)
        assert (tmp_path / "new-cache" / "test.txt").read_text(encoding="utf-8") == "hello"

    def test_no_migration_when_old_missing(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        old_dir = str(tmp_path / "old-data")
        new_dir = str(tmp_path / "new-cache")

        monkeypatch.setattr("virtualenv.app_data.user_cache_dir", lambda **_kw: new_dir)
        monkeypatch.setattr("virtualenv.app_data.user_data_dir", lambda **_kw: old_dir)

        result = _cache_dir_with_migration()
        assert result == new_dir
        assert not os.path.isdir(old_dir)

    def test_no_migration_when_new_exists(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        old_dir = str(tmp_path / "old-data")
        new_dir = str(tmp_path / "new-cache")
        os.makedirs(old_dir)
        os.makedirs(new_dir)
        (tmp_path / "old-data" / "old.txt").write_text("old", encoding="utf-8")

        monkeypatch.setattr("virtualenv.app_data.user_cache_dir", lambda **_kw: new_dir)
        monkeypatch.setattr("virtualenv.app_data.user_data_dir", lambda **_kw: old_dir)

        result = _cache_dir_with_migration()
        assert result == new_dir
        assert os.path.isdir(old_dir)

    def test_same_dir_returns_immediately(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        same_dir = str(tmp_path / "same")
        monkeypatch.setattr("virtualenv.app_data.user_cache_dir", lambda **_kw: same_dir)
        monkeypatch.setattr("virtualenv.app_data.user_data_dir", lambda **_kw: same_dir)

        result = _cache_dir_with_migration()
        assert result == same_dir

    def test_fallback_on_migration_error(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        old_dir = str(tmp_path / "old-data")
        new_dir = str(tmp_path / "new-cache")
        os.makedirs(old_dir)

        monkeypatch.setattr("virtualenv.app_data.user_cache_dir", lambda **_kw: new_dir)
        monkeypatch.setattr("virtualenv.app_data.user_data_dir", lambda **_kw: old_dir)

        def broken_move(_src: str, _dst: str) -> None:
            msg = "permission denied"
            raise OSError(msg)

        monkeypatch.setattr("virtualenv.app_data.shutil.move", broken_move)

        result = _cache_dir_with_migration()
        assert result == old_dir

    @pytest.mark.parametrize("symlink_flag", [True, False])
    def test_symlink_app_data_survives_migration(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        symlink_flag: bool,  # ruff:ignore[unused-method-argument]
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

        monkeypatch.setattr("virtualenv.app_data.user_cache_dir", lambda **_kw: new_dir)
        monkeypatch.setattr("virtualenv.app_data.user_data_dir", lambda **_kw: old_dir)

        result = _cache_dir_with_migration()
        assert result == new_dir
        assert (tmp_path / "new-cache" / "wheel" / "3.12" / "image" / "pip" / "pip.dist-info" / "METADATA").exists()


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
def test_app_data_preserves_setgid_and_read_access(app_data_default: Path) -> None:
    app_data_default.mkdir()
    app_data_default.chmod(0o2775)
    make_app_data(None, read_only=False, env={})
    assert app_data_default.stat().st_mode & 0o7777 == 0o2775


@pytest.mark.skipif(os.name != "posix", reason="POSIX ownership")
def test_app_data_keeps_writable_non_owned_cache(app_data_default: Path, mocker: MockerFixture) -> None:
    app_data_default.mkdir()
    app_data_default.chmod(0o1777)
    mocker.patch("virtualenv.app_data.os.geteuid", autospec=True, return_value=app_data_default.stat().st_uid + 1)
    mocker.patch("virtualenv.app_data.os.chmod", autospec=True, side_effect=PermissionError)
    data: Final = make_app_data(None, read_only=False, env={})
    assert (isinstance(data, AppDataDiskFolder), str(data), app_data_default.stat().st_mode & 0o7777) == (
        True,
        str(app_data_default),
        0o1777,
    )
