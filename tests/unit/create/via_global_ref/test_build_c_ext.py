from __future__ import annotations

import logging
import os
import shutil
import subprocess
from pathlib import Path
from subprocess import Popen

import pytest

from virtualenv.cache import FileCache
from virtualenv.discovery.py_info import PythonInfo
from virtualenv.run import cli_run
from virtualenv.run.plugin.creators import CreatorSelector

logger = logging.getLogger(__name__)


@pytest.mark.slow
@pytest.mark.xfail(
    condition=bool(os.environ.get("CI_RUN")),
    strict=False,
    reason="did not manage to setup CI to run with VC 14.1 C++ compiler, but passes locally",
)
def test_can_build_c_extensions(tmp_path, coverage_env, session_app_data):
    cache = FileCache(session_app_data.py_info, session_app_data.py_info_clear)
    current = PythonInfo.current_system(session_app_data, cache)
    creator_classes = CreatorSelector.for_interpreter(current).key_to_class

    logger.warning("system_include: %s", current.system_include)
    logger.warning("system_include exists: %s", Path(current.system_include).exists())

    def builtin_shows_marker_missing():
        builtin_classs = creator_classes.get("builtin")
        if builtin_classs is None:
            return False
        host_include_marker = getattr(builtin_classs, "host_include_marker", None)
        if host_include_marker is None:
            return False
        marker = host_include_marker(current)
        logger.warning("builtin marker: %s", marker)
        logger.warning("builtin marker exists: %s", marker.exists())
        return not marker.exists()

    system_include = current.system_include
    if not Path(system_include).exists() and not builtin_shows_marker_missing():
        pytest.skip("Building C-Extensions requires header files with host python")

    for creator in [i for i in creator_classes if i != "builtin"]:
        env, greet = tmp_path / creator / "env", str(tmp_path / creator / "greet")
        shutil.copytree(str(Path(__file__).parent.resolve() / "greet"), greet)
        session = cli_run(["--creator", creator, "--seeder", "app-data", str(env), "-vvv"])
        coverage_env()
        setuptools_index_args = ()
        if current.version_info >= (3, 12):
            # requires to be able to install setuptools as build dependency
            setuptools_index_args = (
                "--find-links",
                "https://pypi.org/simple/setuptools/",
            )

        cmd = [
            str(session.creator.script("pip")),
            "install",
            "--no-index",
            *setuptools_index_args,
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
            encoding="utf-8",
        )
        out, _ = process.communicate()
        assert process.returncode == 0
        assert out == "Hello World!\n"
