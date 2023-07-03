from __future__ import annotations

import concurrent.futures
import traceback

import pytest

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
