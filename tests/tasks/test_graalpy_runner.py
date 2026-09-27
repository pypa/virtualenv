from __future__ import annotations

import runpy
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Final

import pytest

if TYPE_CHECKING:
    from collections.abc import Callable

    from pytest_mock import MockerFixture

_CLEAN: Final[str] = '<testsuite tests="1" failures="0" errors="0" skipped="0"/>'
_SHUTDOWN: Final[str] = "did not complete all polyglot threads"


@pytest.fixture
def runner(
    tmp_path: Path, mocker: MockerFixture, capsys: pytest.CaptureFixture[str]
) -> Callable[[int, str, str | None], str]:
    junit_path: Final[Path] = tmp_path / "junit.xml"
    junit_path.write_text(_CLEAN, encoding="utf-8")
    mocker.patch.object(sys, "argv", ["runner", str(junit_path), "--junitxml", str(junit_path)])

    def invoke(status: int, stderr: str, report: str | None) -> str:
        def finish(*_args: list[str], **_kwargs: str | int | bool) -> subprocess.CompletedProcess[str]:
            if report is not None:
                junit_path.write_text(report, encoding="utf-8")
            return subprocess.CompletedProcess([], status, stderr=stderr)

        mocker.patch("subprocess.run", autospec=True, side_effect=finish)
        runpy.run_path(str(Path(__file__).parents[2] / "tasks" / "run_graalpy_tests.py"), run_name="__main__")
        return capsys.readouterr().out

    return invoke


@pytest.mark.parametrize(
    ("status", "stderr", "report", "expected"),
    [
        pytest.param(0, "", None, 0, id="success-without-report"),
        pytest.param(1, _SHUTDOWN, _CLEAN, None, id="known-shutdown"),
        pytest.param(1, _SHUTDOWN, f"<testsuites>{_CLEAN}</testsuites>", None, id="wrapped-suite"),
        pytest.param(1, "unrelated crash", _CLEAN, 1, id="unknown-crash"),
        pytest.param(2, _SHUTDOWN, _CLEAN, 2, id="interrupted"),
        pytest.param(3, _SHUTDOWN, _CLEAN, 3, id="internal-error"),
        pytest.param(4, _SHUTDOWN, _CLEAN, 4, id="usage-error"),
        pytest.param(5, _SHUTDOWN, _CLEAN, 5, id="no-tests-exit"),
        pytest.param(-9, _SHUTDOWN, _CLEAN, -9, id="killed"),
        pytest.param(1, _SHUTDOWN, None, 1, id="stale-report"),
        pytest.param(1, _SHUTDOWN, "<testsuite", 1, id="truncated-report"),
        pytest.param(1, _SHUTDOWN, "<testsuites/>", 1, id="no-suites"),
        pytest.param(1, _SHUTDOWN, _CLEAN.replace('tests="1"', 'tests="0"'), 1, id="zero-tests"),
        pytest.param(1, _SHUTDOWN, _CLEAN.replace('skipped="0"', 'skipped="1"'), 1, id="all-skipped"),
        pytest.param(1, _SHUTDOWN, _CLEAN.replace('failures="0"', 'failures="1"'), 1, id="failed-test"),
        pytest.param(1, _SHUTDOWN, _CLEAN.replace('errors="0"', 'errors="1"'), 1, id="errored-test"),
        pytest.param(1, _SHUTDOWN, _CLEAN.replace('tests="1"', ""), 1, id="missing-count"),
        pytest.param(1, _SHUTDOWN, _CLEAN.replace('tests="1"', 'tests="bad"'), 1, id="invalid-count"),
        pytest.param(
            1,
            _SHUTDOWN,
            f'<testsuites>{_CLEAN}<testsuite tests="1" failures="1" errors="0"/></testsuites>',
            1,
            id="later-suite-fails",
        ),
    ],
)
def test_graalpy_exit_status(
    runner: Callable[[int, str, str | None], str],
    status: int,
    stderr: str,
    report: str | None,
    expected: int | None,
) -> None:
    if expected is None:
        assert runner(status, stderr, report) == (
            "GraalVM reported its known polyglot shutdown error after a completed test run (see #3240).\n"
        )
    else:
        with pytest.raises(SystemExit) as raised:
            runner(status, stderr, report)
        assert raised.value.code == expected
