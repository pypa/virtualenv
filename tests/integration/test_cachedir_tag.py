from __future__ import annotations

import shutil
import sys
from subprocess import check_output, run
from typing import TYPE_CHECKING

import pytest

from virtualenv import cli_run

if TYPE_CHECKING:
    from pathlib import Path

# gtar => gnu-tar on macOS
TAR = next((target for target in ("gtar", "tar") if shutil.which(target)), None)


def compatible_is_tar_present() -> bool:
    return TAR and "--exclude-caches" in check_output(args=[TAR, "--help"], text=True)


@pytest.mark.skipif(sys.platform == "win32", reason="Windows does not have tar")
@pytest.mark.skipif(not compatible_is_tar_present(), reason="Compatible tar is not installed")
def test_cachedir_tag_ignored_by_tag(tmp_path: Path) -> None:
    venv = tmp_path / ".venv"
    cli_run(["--activators", "", "--without-pip", str(venv)])

    args = [TAR, "--create", "--file", "/dev/null", "--exclude-caches", "--verbose", venv.name]
    tar_result = run(args=args, capture_output=True, text=True, cwd=tmp_path)
    assert tar_result.stdout == ".venv/\n.venv/CACHEDIR.TAG\n"
    assert tar_result.stderr == f"{TAR}: .venv/: contains a cache directory tag CACHEDIR.TAG; contents not dumped\n"
