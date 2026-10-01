from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, Final

import pytest
from python_discovery import PythonInfo

from virtualenv.run import cli_run
from virtualenv.run.plugin.creators import CreatorSelector
from virtualenv.seed.wheels.embed import BUNDLE_FOLDER as EMBED_WHEEL_DIR

if TYPE_CHECKING:
    from collections.abc import Callable

_CURRENT: Final = PythonInfo.current_system()
_CREATOR_CLASSES: Final = CreatorSelector.for_interpreter(_CURRENT).key_to_class


def builtin_shows_marker_missing() -> bool:
    if (builtin_class := _CREATOR_CLASSES.get("builtin")) is None:
        return False
    if (host_include_marker := getattr(builtin_class, "host_include_marker", None)) is None:
        return False
    return not host_include_marker(_CURRENT).exists()


@pytest.mark.slow
@pytest.mark.timeout(300)
@pytest.mark.xfail(
    condition=bool(os.environ.get("CI_RUN")),
    strict=False,
    reason="did not manage to setup CI to run with VC 14.1 C++ compiler, but passes locally",
)
@pytest.mark.skipif(
    not Path(_CURRENT.system_include).exists() and not builtin_shows_marker_missing(),
    reason="Building C-Extensions requires header files with host python",
)
@pytest.mark.parametrize("creator", [i for i in _CREATOR_CLASSES if i != "builtin"])
def test_can_build_c_extensions(creator: str, tmp_path: Path, coverage_env: Callable[[], None]) -> None:
    greet = str(tmp_path / "greet")
    shutil.copytree(str(Path(__file__).parent.resolve() / "greet"), greet)
    session = cli_run(["--creator", creator, "--seeder", "app-data", str(tmp_path / "env"), "-vvv"])
    coverage_env()
    cmd = [
        str(session.creator.exe),
        "-m",
        "pip",
        "install",
        "--no-index",
        "--find-links",
        str(EMBED_WHEEL_DIR),
        "--no-deps",
        "--disable-pip-version-check",
        "-vvv",
        greet,
    ]
    # xdist workers on Windows send child output to NUL and pytest-timeout can only os._exit() them there, so bound
    # the build here and keep its log: a stall then fails this test with the output instead of killing the worker
    with (log := tmp_path / "pip.log").open("w", encoding="utf-8") as stream:
        try:
            build = subprocess.run(cmd, stdout=stream, stderr=subprocess.STDOUT, timeout=180, check=False)
        except subprocess.TimeoutExpired:
            pytest.fail(f"pip install did not finish in 180s:\n{log.read_text(encoding='utf-8')}")
    assert build.returncode == 0, log.read_text(encoding="utf-8")

    result = subprocess.run(
        [str(session.creator.exe), "-c", "import greet; greet.greet('World')"],
        capture_output=True,
        encoding="utf-8",
        timeout=60,
        check=False,
    )
    assert (result.returncode, result.stdout) == (0, "Hello World!\n"), result.stderr
