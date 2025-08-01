from __future__ import annotations

import os
import sys

import pytest

from virtualenv.run import cli_run


@pytest.mark.skipif(sys.platform == "win32", reason="resource module not available on Windows")
def test_too_many_open_files(tmp_path):
    """
    Test that we get a specific error message when we have too many open files.
    """
    import resource  # noqa: PLC0415

    soft_limit, hard_limit = resource.getrlimit(resource.RLIMIT_NOFILE)
    if soft_limit > 1024:
        pytest.skip("soft limit for open files is too high to reliably trigger the error")

    # Lower the soft limit to a small number to trigger the error
    try:
        resource.setrlimit(resource.RLIMIT_NOFILE, (32, hard_limit))
    except ValueError:
        pytest.skip("could not lower the soft limit for open files")

    # Keep some file descriptors open to make it easier to trigger the error
    fds = []
    try:
        fds.extend(os.open(os.devnull, os.O_RDONLY) for _ in range(20))

        with pytest.raises(SystemExit) as excinfo:
            cli_run([str(tmp_path / "venv")])

        assert excinfo.value.code != 0

    finally:
        for fd in fds:
            os.close(fd)
        resource.setrlimit(resource.RLIMIT_NOFILE, (soft_limit, hard_limit))
