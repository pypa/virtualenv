from __future__ import annotations

import concurrent.futures
import os
import traceback

import pytest

from virtualenv.app_data import _cache_dir_with_migration, _default_app_data_dir
from virtualenv.util.lock import ReentrantFileLock
from virtualenv.util.subprocess import run_cmd


def test_run_fail(tmp_path):
    code, out, err = run_cmd([str(tmp_path)])
    assert err
    assert not out
    assert code


def test_reentrant_file_lock_is_thread_safe(tmp_path):
    lock = ReentrantFileLock(tmp_path)
    target_file = tmp_path / "target"
    target_file.touch()

    def recreate_target_file():
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
    def test_override_env_var(self, tmp_path):
        custom = str(tmp_path / "custom")
        env = {"VIRTUALENV_OVERRIDE_APP_DATA": custom}
        assert _default_app_data_dir(env) == custom

    def test_no_override_returns_cache_dir(self, monkeypatch):
        monkeypatch.delenv("VIRTUALENV_OVERRIDE_APP_DATA", raising=False)
        result = _default_app_data_dir(os.environ)
        assert result


class TestCacheDirMigration:
    def test_migrate_old_to_new(self, tmp_path, monkeypatch):
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

    def test_no_migration_when_old_missing(self, tmp_path, monkeypatch):
        old_dir = str(tmp_path / "old-data")
        new_dir = str(tmp_path / "new-cache")

        monkeypatch.setattr("virtualenv.app_data.user_cache_dir", lambda **_kw: new_dir)
        monkeypatch.setattr("virtualenv.app_data.user_data_dir", lambda **_kw: old_dir)

        result = _cache_dir_with_migration()
        assert result == new_dir
        assert not os.path.isdir(old_dir)

    def test_no_migration_when_new_exists(self, tmp_path, monkeypatch):
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

    def test_same_dir_returns_immediately(self, tmp_path, monkeypatch):
        same_dir = str(tmp_path / "same")
        monkeypatch.setattr("virtualenv.app_data.user_cache_dir", lambda **_kw: same_dir)
        monkeypatch.setattr("virtualenv.app_data.user_data_dir", lambda **_kw: same_dir)

        result = _cache_dir_with_migration()
        assert result == same_dir

    def test_fallback_on_migration_error(self, tmp_path, monkeypatch):
        old_dir = str(tmp_path / "old-data")
        new_dir = str(tmp_path / "new-cache")
        os.makedirs(old_dir)

        monkeypatch.setattr("virtualenv.app_data.user_cache_dir", lambda **_kw: new_dir)
        monkeypatch.setattr("virtualenv.app_data.user_data_dir", lambda **_kw: old_dir)

        def broken_move(_src, _dst):
            msg = "permission denied"
            raise OSError(msg)

        monkeypatch.setattr("virtualenv.app_data.shutil.move", broken_move)

        result = _cache_dir_with_migration()
        assert result == old_dir

    @pytest.mark.parametrize("symlink_flag", [True, False])
    def test_symlink_app_data_survives_migration(self, tmp_path, monkeypatch, symlink_flag):  # noqa: ARG002
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
