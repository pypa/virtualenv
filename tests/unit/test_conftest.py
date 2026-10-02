from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Callable

pytest_plugins = ["pytester"]


@pytest.fixture
def collect(pytester: pytest.Pytester, request: pytest.FixtureRequest) -> Callable[[str], pytest.RunResult]:
    # definition order differs from ID order, so slicing the collection order would pick other tests
    pytester.makepyfile(
        test_sample="def test_c(): pass\ndef test_a(): pass\ndef test_d(): pass\ndef test_b(): pass\ndef test_e(): pass\n"
    )

    def run(shard: str) -> pytest.RunResult:
        # registered under a new name, the suite conftest cannot find itself to reorder around pytest-randomly
        return pytester.runpytest_inprocess(
            "-p",
            "no:randomly",
            "--collect-only",
            "-q",
            shard,
            plugins=[request.config.pluginmanager.getplugin(str(Path(__file__).parents[1] / "conftest.py"))],
        )

    return run


@pytest.mark.parametrize(
    ("shard", "expected"),
    [
        pytest.param("--shard=1/2", ["test_c", "test_a", "test_e"], id="first"),
        pytest.param("--shard=2/2", ["test_d", "test_b"], id="second"),
        pytest.param("--shard=1/1", ["test_c", "test_a", "test_d", "test_b", "test_e"], id="single"),
    ],
)
def test_shard_selects_every_nth_test_id(
    collect: Callable[[str], pytest.RunResult], shard: str, expected: list[str]
) -> None:
    result = collect(shard)
    assert [line.split("::")[1] for line in result.outlines if "::" in line] == expected


def test_shard_reports_deselected(collect: Callable[[str], pytest.RunResult]) -> None:
    collect("--shard=2/2").stdout.fnmatch_lines(["2/5 tests collected (3 deselected) in *"])


@pytest.mark.parametrize("value", ["0/2", "3/2", "a/2", "1", "1/2/3"])
def test_shard_rejects_invalid_spec(collect: Callable[[str], pytest.RunResult], value: str) -> None:
    result = collect(f"--shard={value}")
    assert result.ret == pytest.ExitCode.USAGE_ERROR
    result.stderr.fnmatch_lines([f"*argument --shard: expected K/N with 1 <= K <= N, got '{value}'"])
