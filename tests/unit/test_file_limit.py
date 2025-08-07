from __future__ import annotations

import errno
import os
import sys

import pytest

from virtualenv.info import IMPLEMENTATION
from virtualenv.run import cli_run


@pytest.mark.skipif(sys.platform == "win32", reason="resource module not available on Windows")
def test_too_many_open_files(tmp_path):
    """
    Test that we get a specific error message when we have too many open files.
    """
    import resource  # noqa: PLC0415

    soft_limit, hard_limit = resource.getrlimit(resource.RLIMIT_NOFILE)

    # Lower the soft limit to a small number to trigger the error
    try:
        resource.setrlimit(resource.RLIMIT_NOFILE, (32, hard_limit))
    except ValueError:
        pytest.skip("could not lower the soft limit for open files")
    except AttributeError as exc:  # pypy, graalpy
        if "module 'resource' has no attribute 'setrlimit'" in str(exc):
            pytest.skip(f"{IMPLEMENTATION} does not support resource.setrlimit")

    # Keep some file descriptors open to make it easier to trigger the error
    fds = []
    try:
        # JIT implementations use more file descriptors up front so we can run out early
        try:
            fds.extend(os.open(os.devnull, os.O_RDONLY) for _ in range(20))
        except OSError as jit_exceptions:  # pypy, graalpy
            assert jit_exceptions.errno == errno.EMFILE  # noqa: PT017
            assert "Too many open files" in str(jit_exceptions)  # noqa: PT017

        expected_exceptions = SystemExit, OSError, RuntimeError
        with pytest.raises(expected_exceptions) as too_many_open_files_exc:
            cli_run([str(tmp_path / "venv")])

        if isinstance(too_many_open_files_exc, SystemExit):
            assert too_many_open_files_exc.code != 0
        else:
            assert "Too many open files" in str(too_many_open_files_exc.value)

    finally:
        for fd in fds:
            os.close(fd)
        resource.setrlimit(resource.RLIMIT_NOFILE, (soft_limit, hard_limit))
