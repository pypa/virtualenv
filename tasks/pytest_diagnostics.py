"""Keep stack evidence when pytest stalls outside a test's timeout window."""

from __future__ import annotations

import atexit
import faulthandler
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Final

import pytest

if TYPE_CHECKING:
    from typing import TextIO


# faulthandler has one timer per process, including nested pytest sessions.
_DIAGNOSTICS: Final[list[_Diagnostics]] = []


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--diagnostics-dir",
        type=Path,
        default=Path(".tox/hang-diagnostics"),
        help="directory for per-process stack dumps and test events",
    )
    parser.addoption("--diagnostics-interval", type=float, default=60, help="seconds between stack dumps")


@pytest.hookimpl(trylast=True)
def pytest_configure(config: pytest.Config) -> None:
    interval: Final[float] = config.getoption("diagnostics_interval")
    if interval <= 0:
        msg = "--diagnostics-interval must be positive"
        raise pytest.UsageError(msg)
    if not _DIAGNOSTICS:
        _DIAGNOSTICS.append(_Diagnostics(config.getoption("diagnostics_dir"), interval))
    config.pluginmanager.register(_DIAGNOSTICS[0], "session-diagnostics")
    _DIAGNOSTICS[0].retain_crash_traceback()


class _Diagnostics:
    def __init__(self, directory: Path, interval: float) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        worker: Final[str] = os.environ.get("PYTEST_XDIST_WORKER", "controller")
        self.stream: Final[TextIO] = (directory / f"{worker}-{os.getpid()}.log").open(
            "w", encoding="utf-8", buffering=1
        )
        self.interval: Final[float] = interval
        self._record(f"START pid={os.getpid()} parent={os.getppid()} python={sys.version}")
        self._arm_timer()
        atexit.register(self._close)

    def _record(self, message: str) -> None:
        self.stream.write(f"{datetime.now(timezone.utc).isoformat()} {message}\n")

    def _arm_timer(self) -> None:
        faulthandler.dump_traceback_later(self.interval, repeat=True, file=self.stream)

    def retain_crash_traceback(self) -> None:
        # pytest's captured stderr can disappear with a crashed xdist worker.
        faulthandler.enable(file=self.stream)

    def pytest_runtest_logstart(self, nodeid: str) -> None:
        self._record(f"TEST {nodeid}")

    def pytest_runtest_logreport(self, report: pytest.TestReport) -> None:
        self._record(f"{report.when} {report.outcome} {report.nodeid}")

    @pytest.hookimpl(trylast=True)
    def pytest_exception_interact(self) -> None:
        # pytest's faulthandler plugin cancels the timer when reporting an exception.
        self._arm_timer()

    @pytest.hookimpl(trylast=True)
    def pytest_unconfigure(self) -> None:
        self.retain_crash_traceback()
        self._record("STOP")

    def _close(self) -> None:
        # Keep the watchdog alive during xdist worker shutdown, after pytest has returned.
        faulthandler.cancel_dump_traceback_later()
        faulthandler.disable()
        self._record("EXIT")
        self.stream.close()


__all__ = ["pytest_addoption", "pytest_configure"]
