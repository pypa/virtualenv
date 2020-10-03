from __future__ import absolute_import, unicode_literals

from argparse import Namespace

import pytest

from virtualenv.activation import (
    BashActivator,
    BatchActivator,
    CShellActivator,
    FishActivator,
    PowerShellActivator,
    PythonActivator,
)
from virtualenv.discovery.py_info import PythonInfo
from virtualenv.info import IS_WIN
from virtualenv.util.path import Path


@pytest.mark.parametrize(
    "activator_class",
    [BatchActivator, PowerShellActivator, PythonActivator, BashActivator, FishActivator],
)
def test_activator_support_windows(mocker, activator_class):
    activator = activator_class(Namespace(prompt=None))

    interpreter = mocker.Mock(spec=PythonInfo)
    interpreter.os = "nt"
    assert activator.supports(interpreter)


@pytest.mark.parametrize("activator_class", [CShellActivator])
def test_activator_no_support_windows(mocker, activator_class):
    activator = activator_class(Namespace(prompt=None))

    interpreter = mocker.Mock(spec=PythonInfo)
    interpreter.os = "nt"
    assert not activator.supports(interpreter)


@pytest.mark.parametrize(
    "activator_class",
    [BashActivator, CShellActivator, FishActivator, PowerShellActivator, PythonActivator],
)
def test_activator_support_posix(mocker, activator_class):
    activator = activator_class(Namespace(prompt=None))
    interpreter = mocker.Mock(spec=PythonInfo)
    interpreter.os = "posix"
    assert activator.supports(interpreter)


@pytest.mark.parametrize("activator_class", [BatchActivator])
def test_activator_no_support_posix(mocker, activator_class):
    activator = activator_class(Namespace(prompt=None))
    interpreter = mocker.Mock(spec=PythonInfo)
    interpreter.os = "posix"
    assert not activator.supports(interpreter)


class Creator:
    def __init__(self):
        self.dest = "C:/tools/msys64/home"
        self.env_name = "venv"
        self.bin_dir = Path("C:/tools/msys64/home/bin")


@pytest.mark.skipif(IS_WIN, reason="Github Actions ships with WSL bash")
@pytest.mark.parametrize("activator_class", [BashActivator])
def test_cygwin_msys2_path_conversion(mocker, activator_class):
    mocker.patch("sysconfig.get_platform", return_value="mingw")
    activator = activator_class(Namespace(prompt=None))
    creator = Creator()
    mocker.stub(creator.bin_dir.relative_to)
    resource = activator.replacements(creator, "")
    assert resource["__VIRTUAL_ENV__"] == "/c/tools/msys64/home"


@pytest.mark.skipif(IS_WIN, reason="Github Actions ships with WSL bash")
@pytest.mark.parametrize("activator_class", [BashActivator])
def test_win_path_no_conversion(mocker, activator_class):
    mocker.patch("sysconfig.get_platform", return_value="win-amd64")
    activator = activator_class(Namespace(prompt=None))
    creator = Creator()
    mocker.stub(creator.bin_dir.relative_to)
    resource = activator.replacements(creator, "")
    assert resource["__VIRTUAL_ENV__"] == "C:/tools/msys64/home"


@pytest.mark.skipif(IS_WIN, reason="Github Actions ships with WSL bash")
@pytest.mark.parametrize("activator_class", [BashActivator])
def test_cygwin_path_no_conversion(mocker, activator_class):
    mocker.patch("sysconfig.get_platform", return_value="cygwin")
    activator = activator_class(Namespace(prompt=None))
    creator = Creator()
    creator.dest = "/c/tools/msys64/home"
    creator.bin_dir = Path("/c/tools/msys64/home/bin")
    mocker.stub(creator.bin_dir.relative_to)
    resource = activator.replacements(creator, "")
    assert resource["__VIRTUAL_ENV__"] == "/c/tools/msys64/home"
