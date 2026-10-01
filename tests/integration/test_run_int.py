from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from virtualenv import cli_run
from virtualenv.info import IS_PYPY
from virtualenv.seed.wheels.embed import BUNDLE_FOLDER
from virtualenv.util.subprocess import run_cmd

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.graalpy
@pytest.mark.skipif(IS_PYPY, reason="setuptools distutils patching does not work")
def test_app_data_pinning(tmp_path: Path) -> None:
    # pin a bundled wheel served from a search dir: a version absent locally would be downloaded, and a stalled
    # download kills the xdist worker on Windows instead of failing the test
    version = "26.0.1"
    result = cli_run([
        str(tmp_path),
        "--pip",
        version,
        "--extra-search-dir",
        str(BUNDLE_FOLDER),
        "--activators",
        "",
        "--seeder",
        "app-data",
    ])
    code, out, _ = run_cmd([str(result.creator.script("pip")), "list", "--disable-pip-version-check"])
    assert not code
    assert ["pip", version] in [line.split() for line in out.splitlines()]
