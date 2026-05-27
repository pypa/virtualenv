from __future__ import annotations

import errno
import os
import sys
from typing import TYPE_CHECKING

import pytest

from virtualenv.info import IMPLEMENTATION
from virtualenv.run import cli_run

if TYPE_CHECKING:
    from pathlib import Path


def _run_cli_with_full_fds(fds: list[int], tmp_path: Path) -> None:
    try:
        fds.extend(os.open(os.devnull, os.O_RDONLY) for _ in range(20))
    except OSError as jit_exc:  # pypy, graalpy
        assert jit_exc.errno == errno.EMFILE  # noqa: PT017
    with pytest.raises((SystemExit, OSError, RuntimeError)) as excinfo:
        cli_run([str(tmp_path / "venv")])
    exc = excinfo.value
    if isinstance(exc, SystemExit):
        assert exc.code != 0
    elif isinstance(exc, OSError):
        assert exc.errno == errno.EMFILE
    else:
        msg = str(exc)
        assert ("code 24" in msg) or ("errno 24" in msg) or ("EMFILE" in msg)


@pytest.mark.skipif(sys.platform == "win32", reason="resource module not available on Windows")
def test_too_many_open_files(tmp_path) -> None:
    """Test that we get a specific error when we have too many open files."""
    import resource  # noqa: PLC0415

    soft_limit, hard_limit = resource.getrlimit(resource.RLIMIT_NOFILE)

    try:
        resource.setrlimit(resource.RLIMIT_NOFILE, (32, hard_limit))
    except ValueError:
        pytest.skip("could not lower the soft limit for open files")
    except AttributeError as exc:  # pypy, graalpy
        if "module 'resource' has no attribute 'setrlimit'" in str(exc):
            pytest.skip(f"{IMPLEMENTATION} does not support resource.setrlimit")

    fds = []
    try:
        _run_cli_with_full_fds(fds, tmp_path)
    finally:
        for fd in fds:
            os.close(fd)
        resource.setrlimit(resource.RLIMIT_NOFILE, (soft_limit, hard_limit))
