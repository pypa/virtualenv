from __future__ import absolute_import, unicode_literals

import os
import shutil
import subprocess

import pytest

from virtualenv.discovery.py_info import PythonInfo
from virtualenv.run import cli_run
from virtualenv.util.path import Path
from virtualenv.util.subprocess import Popen

CURRENT = PythonInfo.current_system()
CREATOR_CLASSES = CURRENT.creators().key_to_class


def builtin_shows_marker_missing():
    builtin_classs = CREATOR_CLASSES.get("builtin")
    if builtin_classs is None:
        return False
    host_include_marker = getattr(builtin_classs, "host_include_marker", None)
    if host_include_marker is None:
        return False
    marker = host_include_marker(CURRENT)
    return not marker.exists()


@pytest.mark.xfail(
    condition=bool(os.environ.get(str("CI_RUN"))),
    strict=False,
    reason="did not manage to setup CI to run with VC 14.1 C++ compiler, but passes locally",
)
@pytest.mark.skipif(
    not Path(CURRENT.system_include).exists() and not builtin_shows_marker_missing(),
    reason="Building C-Extensions requires header files with host python",
)
@pytest.mark.parametrize("creator", list(i for i in CREATOR_CLASSES.keys() if i != "builtin"))
def test_can_build_c_extensions(creator, tmp_path, coverage_env):
    env, greet = tmp_path / "env", str(tmp_path / "greet")
    shutil.copytree(str(Path(__file__).parent.resolve() / "greet"), greet)
    session = cli_run(["--creator", creator, "--seeder", "app-data", str(env), "-vvv"])
    coverage_env()
    cmd = [
        str(session.creator.script("pip")),
        "install",
        "--no-index",
        "--no-deps",
        "--disable-pip-version-check",
        "-vvv",
        greet,
    ]
    process = Popen(cmd)
    process.communicate()
    assert process.returncode == 0

    process = Popen(
        [str(session.creator.exe), "-c", "import greet; greet.greet('World')"],
        universal_newlines=True,
        stdout=subprocess.PIPE,
    )
    out, _ = process.communicate()
    assert process.returncode == 0
    assert out == "Hello World!\n"
