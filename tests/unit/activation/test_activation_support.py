from __future__ import annotations

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
