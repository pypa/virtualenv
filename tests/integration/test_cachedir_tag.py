from __future__ import annotations

import shutil
import subprocess
import sys

import pytest

from virtualenv import cli_run


@pytest.fixture(scope="session")
def tar_test_env(tmp_path_factory):
    base_path = tmp_path_factory.mktemp("tar-cachedir-test")
    cli_run(["--activators", "", "--without-pip", str(base_path / ".venv")])
    yield base_path
    shutil.rmtree(str(base_path))


def compatible_is_tar_present() -> bool:
    try:
        tar_result = subprocess.run(args=["tar", "--help"], capture_output=True, encoding="utf-8")
        return tar_result.stdout.find("--exclude-caches") > -1
    except FileNotFoundError:
        return False


@pytest.mark.skipif(sys.platform == "win32", reason="Windows does not have tar")
@pytest.mark.skipif(not compatible_is_tar_present(), reason="Compatible tar is not installed")
def test_cachedir_tag_ignored_by_tag(tar_test_env):  # noqa: ARG001
    tar_result = subprocess.run(
        args=["tar", "--create", "--file", "/dev/null", "--exclude-caches", "--verbose", ".venv"],
        capture_output=True,
        encoding="utf-8",
    )
    assert tar_result.stdout == ".venv/\n.venv/CACHEDIR.TAG\n"
    assert tar_result.stderr == "tar: .venv/: contains a cache directory tag CACHEDIR.TAG; contents not dumped\n"
