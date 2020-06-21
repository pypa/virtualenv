"""
It's possible to use multiple types of host pythons to create virtual environments and all should work:

- host installation
- invoking from a venv (if Python 3.3+)
- invoking from an old style virtualenv (<17.0.0)
- invoking from our own venv
"""
from __future__ import absolute_import, unicode_literals

import subprocess
import sys

import pytest

from virtualenv.discovery.py_info import PythonInfo
from virtualenv.run import cli_run
from virtualenv.util.path import Path
from virtualenv.util.subprocess import Popen

CURRENT = PythonInfo.current_system()


# noinspection PyUnusedLocal
def root(tmp_path_factory, session_app_data):
    return CURRENT.system_executable


def venv(tmp_path_factory, session_app_data):
    if CURRENT.is_venv:
        return sys.executable
    elif CURRENT.version_info.major == 3:
        root_python = root(tmp_path_factory, session_app_data)
        dest = tmp_path_factory.mktemp("venv")
        process = Popen([str(root_python), "-m", "venv", "--without-pip", str(dest)])
        process.communicate()
        # sadly creating a virtual environment does not tell us where the executable lives in general case
        # so discover using some heuristic
        exe_path = CURRENT.discover_exe(prefix=str(dest)).original_executable
        return exe_path


def old_virtualenv(tmp_path_factory, session_app_data):
    if CURRENT.is_old_virtualenv:
        return CURRENT.executable
    else:
        env_for_old_virtualenv = tmp_path_factory.mktemp("env-for-old-virtualenv")
        result = cli_run(["--no-download", "--activators", "", str(env_for_old_virtualenv), "--no-periodic-update"])
        # noinspection PyBroadException
        try:
            process = Popen(
                [
                    str(result.creator.script("pip")),
                    "install",
                    "--no-index",
                    "--disable-pip-version-check",
                    str(Path(__file__).resolve().parent / "virtualenv-16.7.9-py2.py3-none-any.whl"),
                    "-v",
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            _, __ = process.communicate()
            assert not process.returncode
        except Exception:
            return RuntimeError("failed to install old virtualenv")
        # noinspection PyBroadException
        try:
            old_virtualenv_at = tmp_path_factory.mktemp("old-virtualenv")
            cmd = [
                str(result.creator.script("virtualenv")),
                str(old_virtualenv_at),
                "--no-pip",
                "--no-setuptools",
                "--no-wheel",
            ]
            process = Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            _, __ = process.communicate()
            assert not process.returncode
            exe_path = CURRENT.discover_exe(session_app_data, prefix=str(old_virtualenv_at)).original_executable
            return exe_path
        except Exception as exception:
            return RuntimeError("failed to create old virtualenv {}".format(exception))


PYTHON = {"root": root, "venv": venv, "old_virtualenv": old_virtualenv}


@pytest.fixture(params=list(PYTHON.values()), ids=list(PYTHON.keys()), scope="session")
def python(request, tmp_path_factory, session_app_data):
    result = request.param(tmp_path_factory, session_app_data)
    if isinstance(result, Exception):
        pytest.skip("could not resolve interpreter based on {} because {}".format(request.param.__name__, result))
    if result is None:
        pytest.skip("requires interpreter with {}".format(request.param.__name__))
    return result
