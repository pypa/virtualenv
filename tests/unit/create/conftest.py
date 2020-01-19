"""
It's possible to use multiple types of host pythons to create virtual environments and all should work:

- host installation
- invoking from a venv (if Python 3.3+)
- invoking from an old style virtualenv (<17.0.0)
- invoking from our own venv
"""
from __future__ import absolute_import, unicode_literals

import sys

import pytest

from virtualenv.discovery.py_info import CURRENT
from virtualenv.info import IS_WIN
from virtualenv.util.subprocess import Popen


# noinspection PyUnusedLocal
def root(tmp_path_factory):
    return CURRENT.system_executable


def venv(tmp_path_factory):
    if CURRENT.is_venv:
        return sys.executable
    elif CURRENT.version_info.major == 3:
        root_python = root(tmp_path_factory)
        dest = tmp_path_factory.mktemp("venv")
        process = Popen([str(root_python), "-m", "venv", "--without-pip", str(dest)])
        process.communicate()
        # sadly creating a virtual environment does not tell us where the executable lives in general case
        # so discover using some heuristic
        return CURRENT.find_exe_based_of(inside_folder=str(dest))


def virtualenv(tmp_path_factory):
    if CURRENT.is_old_virtualenv:
        return CURRENT.executable
    elif CURRENT.version_info.major == 3:
        # noinspection PyCompatibility
        from venv import EnvBuilder

        virtualenv_at = str(tmp_path_factory.mktemp("venv-for-virtualenv"))
        builder = EnvBuilder(symlinks=not IS_WIN)
        builder.create(virtualenv_at)
        venv_for_virtualenv = CURRENT.find_exe_based_of(inside_folder=virtualenv_at)
        cmd = venv_for_virtualenv, "-m", "pip", "install", "virtualenv==16.6.1"
        process = Popen(cmd)
        _, __ = process.communicate()
        assert not process.returncode

        virtualenv_python = tmp_path_factory.mktemp("virtualenv")
        cmd = venv_for_virtualenv, "-m", "virtualenv", virtualenv_python
        process = Popen(cmd)
        _, __ = process.communicate()
        assert not process.returncode
        return CURRENT.find_exe_based_of(inside_folder=virtualenv_python)


PYTHON = {"root": root, "venv": venv, "virtualenv": virtualenv}


@pytest.fixture(params=list(PYTHON.values()), ids=list(PYTHON.keys()), scope="session")
def python(request, tmp_path_factory):
    result = request.param(tmp_path_factory)
    if result is None:
        pytest.skip("could not resolve interpreter based on {}".format(request.param.__name__))
    return result
