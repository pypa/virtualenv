from __future__ import annotations

import io
import os
import runpy
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Final
from unittest.mock import create_autospec

import pytest

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence
    from unittest.mock import MagicMock

    from pytest_mock import MockerFixture

_CLEAN: Final[str] = '<testsuite tests="1" failures="0" errors="0" skipped="0"/>'
_EMPTY: Final[str] = '<testsuite tests="0" failures="0" errors="0" skipped="0"/>'
_SHUTDOWN: Final[str] = "did not complete all polyglot threads"
_PASS: Final[tuple[int, str, str | None]] = (0, "", _CLEAN)
_POPEN: Final[type[subprocess.Popen[str]]] = subprocess.Popen  # the fixture patches the module attribute
_RUNNER: Final[Path] = Path(__file__).parents[2] / "tasks" / "run_graalpy_tests.py"

Outcome = tuple[int, str, "str | None"]


@pytest.fixture
def junit(tmp_path: Path) -> Path:
    return tmp_path / "junit.xml"


@pytest.fixture
def popen(mocker: MockerFixture, junit: Path) -> Callable[[Sequence[Outcome]], MagicMock]:
    def install(outcomes: Sequence[Outcome]) -> MagicMock:
        for index in range(1, len(outcomes) + 1):
            junit.with_suffix(f".{index}.xml").write_text(_CLEAN, encoding="utf-8")  # a stale report from a prior run

        def start(command: list[str], **_kwargs: object) -> MagicMock:
            index = int(command[-3].removeprefix("--shard=").split("/")[0])
            status, stderr, report = outcomes[index - 1]
            if report is not None:
                Path(command[-1]).write_text(report, encoding="utf-8")
            process = create_autospec(
                _POPEN, instance=True, stdout=io.StringIO(f"collected {index}\n"), stderr=io.StringIO(stderr)
            )
            # Python 3.11 autospec replaces a child configured through create_autospec kwargs
            process.wait.return_value = status
            return process

        return mocker.patch("subprocess.Popen", autospec=True, side_effect=start)

    return install


@pytest.fixture
def run_shards(
    mocker: MockerFixture, junit: Path, popen: Callable[[Sequence[Outcome]], MagicMock]
) -> Callable[[Sequence[Outcome]], MagicMock]:
    def invoke(outcomes: Sequence[Outcome]) -> MagicMock:
        started = popen(outcomes)
        mocker.patch.object(sys, "argv", ["runner", "--shards", str(len(outcomes)), str(junit), "tests"])
        runpy.run_path(str(_RUNNER), run_name="__main__")
        return started

    return invoke


@pytest.mark.parametrize(
    "outcomes",
    [
        pytest.param([_PASS, _PASS], id="clean"),
        pytest.param([(1, _SHUTDOWN, _CLEAN), _PASS], id="known-shutdown"),
        pytest.param([(1, _SHUTDOWN, f"<testsuites>{_CLEAN}</testsuites>"), _PASS], id="wrapped-suite"),
        pytest.param([(5, "", _EMPTY), _PASS], id="shard-without-tests"),
        pytest.param([(1, _SHUTDOWN, _EMPTY), _PASS], id="shutdown-without-tests"),
    ],
)
def test_graalpy_shards_pass(run_shards: Callable[[Sequence[Outcome]], MagicMock], outcomes: list[Outcome]) -> None:
    run_shards(outcomes)


@pytest.mark.parametrize(
    "first",
    [
        pytest.param((1, "unrelated crash", _CLEAN), id="unknown-crash"),
        pytest.param((2, _SHUTDOWN, _CLEAN), id="interrupted"),
        pytest.param((3, _SHUTDOWN, _CLEAN), id="internal-error"),
        pytest.param((4, _SHUTDOWN, _CLEAN), id="usage-error"),
        pytest.param((-9, _SHUTDOWN, _CLEAN), id="killed"),
        pytest.param((0, "", None), id="success-without-report"),
        pytest.param((1, _SHUTDOWN, None), id="stale-report"),
        pytest.param((1, _SHUTDOWN, "<testsuite"), id="truncated-report"),
        pytest.param((1, _SHUTDOWN, "<testsuites/>"), id="no-suites"),
        pytest.param((1, _SHUTDOWN, _CLEAN.replace('failures="0"', 'failures="1"')), id="failed-test"),
        pytest.param((1, _SHUTDOWN, _CLEAN.replace('errors="0"', 'errors="1"')), id="errored-test"),
        pytest.param((1, _SHUTDOWN, _CLEAN.replace('tests="1"', "")), id="missing-count"),
        pytest.param((1, _SHUTDOWN, _CLEAN.replace('tests="1"', 'tests="bad"')), id="invalid-count"),
        pytest.param(
            (1, _SHUTDOWN, f'<testsuites>{_CLEAN}<testsuite tests="1" failures="1" errors="0"/></testsuites>'),
            id="later-suite-fails",
        ),
    ],
)
def test_graalpy_shard_fails(run_shards: Callable[[Sequence[Outcome]], MagicMock], first: Outcome) -> None:
    with pytest.raises(SystemExit, match=r"^pytest shards failed: 1/2$"):
        run_shards([first, _PASS])


def test_graalpy_shards_report_every_failure(run_shards: Callable[[Sequence[Outcome]], MagicMock]) -> None:
    with pytest.raises(SystemExit, match=r"^pytest shards failed: 1/2, 2/2$"):
        run_shards([(2, "", _CLEAN), (2, "", _CLEAN)])


@pytest.mark.parametrize(
    "report",
    [
        pytest.param(_EMPTY, id="zero-tests"),
        pytest.param(_CLEAN.replace('skipped="0"', 'skipped="1"'), id="all-skipped"),
    ],
)
def test_graalpy_shards_fail_without_tests(run_shards: Callable[[Sequence[Outcome]], MagicMock], report: str) -> None:
    with pytest.raises(SystemExit, match=r"^pytest shards ran no tests$"):
        run_shards([(5, "", report), (0, "", report)])


def test_graalpy_shard_command(run_shards: Callable[[Sequence[Outcome]], MagicMock], junit: Path) -> None:
    started = run_shards([_PASS, _PASS])
    assert [call.args[0] for call in started.call_args_list] == [
        [sys.executable, "-u", "-m", "pytest", "tests", f"--shard={index}/2", "--junitxml", str(junit.parent / name)]
        for index, name in ((1, "junit.1.xml"), (2, "junit.2.xml"))
    ]


def test_graalpy_shard_output_prefixed(
    run_shards: Callable[[Sequence[Outcome]], MagicMock], capsys: pytest.CaptureFixture[str]
) -> None:
    run_shards([(1, f"{_SHUTDOWN}\n", _CLEAN), _PASS])
    assert capsys.readouterr() == (
        (
            "[1/2] collected 1\n"
            "[2/2] collected 2\n"
            "[1/2] GraalVM reported its known polyglot shutdown error after a completed test run (see #3240).\n"
        ),
        f"[1/2] {_SHUTDOWN}\n",
    )


@pytest.mark.parametrize(
    ("status", "report", "message"),
    [
        pytest.param(2, _CLEAN, "[1/2] exit 2\n", id="exit-status"),
        pytest.param(0, None, "[1/2] exit 0 without a clean junit report\n", id="bad-report"),
    ],
)
def test_graalpy_shard_failure_explained(
    run_shards: Callable[[Sequence[Outcome]], MagicMock],
    capsys: pytest.CaptureFixture[str],
    status: int,
    report: str | None,
    message: str,
) -> None:
    with pytest.raises(SystemExit):
        run_shards([(status, "", report), _PASS])
    assert capsys.readouterr().out.endswith(message)


@pytest.mark.parametrize(
    ("cpu_count", "expected"),
    [pytest.param(3, 3, id="per-cpu"), pytest.param(None, 1, id="unknown-cpu-count")],
)
def test_graalpy_shards_default_to_cpu_count(
    mocker: MockerFixture,
    junit: Path,
    popen: Callable[[Sequence[Outcome]], MagicMock],
    cpu_count: int | None,
    expected: int,
) -> None:
    mocker.patch.object(os, "cpu_count", return_value=cpu_count)
    started = popen([_PASS] * expected)
    mocker.patch.object(sys, "argv", ["runner", str(junit), "tests"])
    runpy.run_path(str(_RUNNER), run_name="__main__")
    assert started.call_count == expected


def test_graalpy_groups_cover_all_shards(
    mocker: MockerFixture, junit: Path, popen: Callable[[Sequence[Outcome]], MagicMock]
) -> None:
    started: Final = popen([_PASS] * 8)
    for group in range(1, 5):
        mocker.patch.object(sys, "argv", ["runner", "--shards", "2", "--group", f"{group}/4", str(junit), "tests"])
        runpy.run_path(str(_RUNNER), run_name="__main__")
    assert sorted(call.args[0][-3] for call in started.call_args_list) == [
        f"--shard={index}/8" for index in range(1, 9)
    ]


@pytest.mark.parametrize("group", ["0/4", "5/4", "1/0", "1", "a/4", "1/2/3"], ids=str)
def test_graalpy_invalid_group(mocker: MockerFixture, junit: Path, group: str) -> None:
    mocker.patch.object(sys, "argv", ["runner", "--group", group, str(junit), "tests"])
    with pytest.raises(SystemExit) as exc:
        runpy.run_path(str(_RUNNER), run_name="__main__")
    assert exc.value.code == 2
