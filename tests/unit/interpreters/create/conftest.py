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

from virtualenv.interpreters.discovery.py_info import CURRENT, IS_WIN


# noinspection PyUnusedLocal
def get_root(tmp_path_factory):
    return CURRENT.system_executable


def get_venv(tmp_path_factory):
    if CURRENT.is_venv:
        return sys.executable
    elif CURRENT.version_info.major == 3:
        root_python = get_root(tmp_path_factory)
        dest = tmp_path_factory.mktemp("venv")
        subprocess.check_call([str(root_python), "-m", "venv", "--without-pip", str(dest)])
        return CURRENT.find_exe(str(dest))


def get_virtualenv(tmp_path_factory):
    if CURRENT.is_old_virtualenv:
        return CURRENT.executable
    elif CURRENT.version_info.major == 3:
        # noinspection PyCompatibility
        from venv import EnvBuilder

        virtualenv_at = str(tmp_path_factory.mktemp("venv-for-virtualenv"))
        builder = EnvBuilder(symlinks=not IS_WIN)
        builder.create(virtualenv_at)
        venv_for_virtualenv = CURRENT.find_exe(virtualenv_at)
        cmd = venv_for_virtualenv, "-m", "pip", "install", "virtualenv==16.6.1"
        subprocess.check_call(cmd)

        virtualenv_python = tmp_path_factory.mktemp("virtualenv")
        cmd = venv_for_virtualenv, "-m", "virtualenv", virtualenv_python
        subprocess.check_call(cmd)
        return CURRENT.find_exe(virtualenv_python)


PYTHON = {"root": get_root, "venv": get_venv, "virtualenv": get_virtualenv}


@pytest.fixture(params=list(PYTHON.values()), ids=list(PYTHON.keys()), scope="session")
def python(request, tmp_path_factory):
    result = request.param(tmp_path_factory)
    if result is None:
        pytest.skip("could not resolve {}".format(request.param))
    return result
