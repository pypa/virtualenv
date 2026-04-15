from __future__ import annotations

import concurrent.futures
import os
import traceback
import zipfile
from typing import TYPE_CHECKING

import pytest

from virtualenv.app_data import _cache_dir_with_migration, _default_app_data_dir
from virtualenv.util import zipapp
from virtualenv.util.lock import ReentrantFileLock
from virtualenv.util.subprocess import run_cmd

if TYPE_CHECKING:
    from pathlib import Path


def test_run_fail(tmp_path) -> None:
    code, out, err = run_cmd([str(tmp_path)])
    assert err
    assert not out
    assert code


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
            except Exception:  # noqa: BLE001, PERF203
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
        (tmp_path / "old-data" / "test.txt").write_text("hello")

        monkeypatch.setattr("virtualenv.app_data.user_cache_dir", lambda **_kw: new_dir)
        monkeypatch.setattr("virtualenv.app_data.user_data_dir", lambda **_kw: old_dir)

        result = _cache_dir_with_migration()
        assert result == new_dir
        assert os.path.isdir(new_dir)
        assert not os.path.isdir(old_dir)
        assert (tmp_path / "new-cache" / "test.txt").read_text() == "hello"

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
        (tmp_path / "old-data" / "old.txt").write_text("old")

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
        symlink_flag: bool,  # noqa: ARG002
    ) -> None:
        old_dir = str(tmp_path / "old-data")
        new_dir = str(tmp_path / "new-cache")
        os.makedirs(old_dir)
        wheel_img = tmp_path / "old-data" / "wheel" / "3.12" / "image" / "pip"
        wheel_img.mkdir(parents=True)
        (wheel_img / "pip.dist-info").mkdir()
        (wheel_img / "pip.dist-info" / "METADATA").write_text("Name: pip")

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


def test_zipapp_read_rejects_path_escaping_via_parent(fake_zipapp_root: Path) -> None:
    escape = fake_zipapp_root / ".." / "escape.txt"
    with pytest.raises(RuntimeError, match="should be within ROOT"):
        zipapp.read(escape)


def test_zipapp_read_rejects_unrelated_absolute_path(fake_zipapp_root: Path, tmp_path: Path) -> None:  # noqa: ARG001
    unrelated = tmp_path / "other" / "file.txt"
    with pytest.raises(RuntimeError, match="should be within ROOT"):
        zipapp.read(unrelated)
