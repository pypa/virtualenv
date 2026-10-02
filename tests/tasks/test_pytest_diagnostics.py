from __future__ import annotations

from pathlib import Path
from typing import Final

import pytest

pytest_plugins = ["pytester"]

_WAIT: Final[str] = """
import os
import time
from pathlib import Path
from typing import Final

def wait_for_stack(function: str) -> None:
    worker: Final[str] = os.environ.get("PYTEST_XDIST_WORKER", "controller")
    path: Final[Path] = Path("diagnostics") / f"{worker}-{os.getpid()}.log"
    deadline: Final[float] = time.monotonic() + 20
    while time.monotonic() < deadline:
        text = path.read_text(encoding="utf-8")
        controller = next(Path("diagnostics").glob("controller-*.log")).read_text(encoding="utf-8")
        if (
            text.count(" DUMP\\n") >= 2
            and f"in {function}\\n" in text
            and all("pytest_runtestloop" in log for log in (text, controller))
        ):
            return
        time.sleep(0.01)
    raise TimeoutError("stack dumps did not capture the blocked pytest process")
"""


@pytest.fixture
def diagnostic_pytester(pytester: pytest.Pytester, monkeypatch: pytest.MonkeyPatch) -> pytest.Pytester:
    monkeypatch.setenv("PYTHONPATH", str(Path(__file__).parents[2]))
    monkeypatch.setenv("PYTEST_DISABLE_PLUGIN_AUTOLOAD", "1")
    monkeypatch.setenv("PYTEST_ADDOPTS", "")
    monkeypatch.delenv("PYTEST_XDIST_WORKER", raising=False)
    pytester.plugins.append("tasks.pytest_diagnostics")
    pytester.makeini("[pytest]\naddopts = --diagnostics-dir=diagnostics --diagnostics-interval=0.05\n")
    return pytester


def test_diagnostics_capture_controller_and_workers(diagnostic_pytester: pytest.Pytester) -> None:
    source: Final[str] = _WAIT + '\ndef test_wait_for_stack() -> None:\n    wait_for_stack("test_wait_for_stack")\n'
    diagnostic_pytester.makepyfile(test_first=source, test_second=source)
    diagnostic_pytester.runpytest_subprocess("-p", "xdist.plugin", "-n", "2", timeout=30).assert_outcomes(passed=2)
    logs: Final[dict[str, str]] = {
        path.name.split("-")[0]: path.read_text(encoding="utf-8")
        for path in (diagnostic_pytester.path / "diagnostics").glob("*.log")
    }
    assert set(logs) == {"controller", "gw0", "gw1"}
    for worker, text in logs.items():
        assert text.count(" DUMP\n") >= 2
        assert "pytest_runtestloop" in text
        assert "pid=" in text
        assert "parent=" in text
        assert "python=" in text
        assert "TEST test_" in text
        assert "call passed test_" in text
        assert text.endswith("EXIT\n")
        if worker != "controller":
            assert "in test_wait_for_stack\n" in text


def test_diagnostics_rearm_after_failure(diagnostic_pytester: pytest.Pytester) -> None:
    diagnostic_pytester.makepyfile(
        _WAIT
        + """
def test_failure() -> None:
    raise RuntimeError("intentional failure")

def test_wait_for_stack() -> None:
    wait_for_stack("test_wait_for_stack")
"""
    )
    result: Final[pytest.RunResult] = diagnostic_pytester.runpytest_subprocess(timeout=30)
    result.assert_outcomes(failed=1, passed=1)
    text: Final[str] = next((diagnostic_pytester.path / "diagnostics").glob("*.log")).read_text(encoding="utf-8")
    assert "call failed" in text
    assert "in test_wait_for_stack\n" in text
    assert " DUMP\n" in text


def test_diagnostics_survive_abrupt_exit(diagnostic_pytester: pytest.Pytester) -> None:
    diagnostic_pytester.makepyfile(
        _WAIT
        + """
def test_wait_for_stack() -> None:
    wait_for_stack("test_wait_for_stack")
    os._exit(23)
"""
    )
    assert diagnostic_pytester.runpytest_subprocess(timeout=30).ret == 23
    text: Final[str] = next((diagnostic_pytester.path / "diagnostics").glob("*.log")).read_text(encoding="utf-8")
    assert "in test_wait_for_stack\n" in text
    assert " DUMP\n" in text
    assert "STOP" not in text


@pytest.mark.parametrize("nested", [False, True], ids=["direct", "after-nested-pytest"])
def test_diagnostics_retain_worker_crash(diagnostic_pytester: pytest.Pytester, nested: bool) -> None:
    diagnostic_pytester.makepyfile(
        inner="def test_inner() -> None: pass",
        outer=f"""
import os
import pytest

def test_crash() -> None:
    if {nested}:
        assert pytest.main(["inner.py", "-p", "tasks.pytest_diagnostics"]) == 0
    os.abort()
""",
    )
    # the watchdog and the fatal handler write to the same file unsynchronized, so keep the watchdog quiet here
    diagnostic_pytester.runpytest_subprocess(
        "outer.py", "-p", "xdist.plugin", "-n", "1", "--max-worker-restart=0", "--diagnostics-interval=60", timeout=30
    ).assert_outcomes(failed=1)
    text: Final[str] = next((diagnostic_pytester.path / "diagnostics").glob("gw0-*.log")).read_text(encoding="utf-8")
    assert "Fatal Python error:" in text
    assert "in test_crash\n" in text


def test_diagnostics_survive_nested_pytest(diagnostic_pytester: pytest.Pytester) -> None:
    diagnostic_pytester.makepyfile(
        inner="def test_inner() -> None: pass",
        outer=_WAIT
        + """
import pytest

def test_wait_after_nested_pytest() -> None:
    assert pytest.main(["inner.py", "-p", "tasks.pytest_diagnostics", "--diagnostics-dir=nested"]) == 0
    wait_for_stack("test_wait_after_nested_pytest")
""",
    )
    diagnostic_pytester.runpytest_subprocess("outer.py", timeout=30).assert_outcomes(passed=1)
    text: Final[str] = next((diagnostic_pytester.path / "diagnostics").glob("*.log")).read_text(encoding="utf-8")
    assert "in test_wait_after_nested_pytest\n" in text


def test_diagnostics_dump_when_gil_held(diagnostic_pytester: pytest.Pytester) -> None:
    # a backtracking regex keeps the GIL for over a second, longer than the stall timer's 10 intervals
    diagnostic_pytester.makepyfile(
        """
import re
import time
from pathlib import Path

def test_hold_the_gil() -> None:
    log = next(Path("diagnostics").glob("controller-*.log"))
    deadline = time.monotonic() + 20
    while "Timeout (" not in log.read_text(encoding="utf-8"):
        assert time.monotonic() < deadline, "the stall timer never fired"
        re.fullmatch(r"(a+)+b", "a" * 26)
"""
    )
    diagnostic_pytester.runpytest_subprocess(timeout=30).assert_outcomes(passed=1)
    text: Final[str] = next((diagnostic_pytester.path / "diagnostics").glob("*.log")).read_text(encoding="utf-8")
    _, header, after = text.partition("Timeout (")
    assert (header, "in test_hold_the_gil\n" in after.split(" DUMP\n", 1)[0]) == ("Timeout (", True)


def test_diagnostics_capture_shutdown_wait(diagnostic_pytester: pytest.Pytester) -> None:
    diagnostic_pytester.makeconftest(
        """
import os
import threading
import time
from pathlib import Path
from typing import Final

def pytest_unconfigure() -> None:
    threading.Thread(target=wait_for_shutdown).start()

def wait_for_shutdown() -> None:
    path: Final[Path] = Path("diagnostics") / f"controller-{os.getpid()}.log"
    deadline: Final[float] = time.monotonic() + 20
    while time.monotonic() < deadline:
        tail = path.read_text(encoding="utf-8").rsplit("STOP\\n", 1)[-1]
        if tail.count("in _shutdown\\n") >= 2 and "in wait_for_shutdown\\n" in tail:
            return
        time.sleep(0.01)
    raise TimeoutError("no stack dump during shutdown")
"""
    )
    diagnostic_pytester.makepyfile("def test_empty() -> None: pass")
    diagnostic_pytester.runpytest_subprocess(timeout=30).assert_outcomes(passed=1)
    text: Final[str] = next((diagnostic_pytester.path / "diagnostics").glob("*.log")).read_text(encoding="utf-8")
    tail: Final[str] = text.rsplit("STOP\n", 1)[-1]
    assert tail.count("in _shutdown\n") >= 2
    assert "in wait_for_shutdown\n" in tail


def test_diagnostics_default_directory(diagnostic_pytester: pytest.Pytester) -> None:
    diagnostic_pytester.makeini("[pytest]\n")
    diagnostic_pytester.makepyfile("def test_empty() -> None: pass")
    diagnostic_pytester.runpytest_subprocess(timeout=30).assert_outcomes(passed=1)
    text: Final[str] = next((diagnostic_pytester.path / ".tox/hang-diagnostics").glob("*.log")).read_text(
        encoding="utf-8"
    )
    assert "call passed test_" in text


def test_diagnostics_reject_nonpositive_interval(diagnostic_pytester: pytest.Pytester) -> None:
    result: Final[pytest.RunResult] = diagnostic_pytester.runpytest_subprocess("--diagnostics-interval=0", timeout=30)
    assert result.ret == pytest.ExitCode.USAGE_ERROR
    result.stderr.fnmatch_lines(["*--diagnostics-interval must be positive*"])
