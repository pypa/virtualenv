from types import SimpleNamespace

import pytest

from virtualenv.activation import (
    BashActivator,
    CShellActivator,
    DOSActivator,
    FishActivator,
    PowerShellActivator,
    PythonActivator,
)
from virtualenv.interpreters.discovery.py_info import PythonInfo


@pytest.mark.parametrize("activator_class", [DOSActivator, PowerShellActivator, PythonActivator])
def test_activator_support_windows(mocker, activator_class):
    activator = activator_class(SimpleNamespace(prompt=None))

    interpreter = mocker.Mock(spec=PythonInfo)
    interpreter.os = "nt"
    assert activator.supports(interpreter)


@pytest.mark.parametrize("activator_class", [BashActivator, CShellActivator, FishActivator])
def test_activator_no_support_windows(mocker, activator_class):
    activator = activator_class(SimpleNamespace(prompt=None))

    interpreter = mocker.Mock(spec=PythonInfo)
    interpreter.os = "nt"
    assert not activator.supports(interpreter)


@pytest.mark.parametrize(
    "activator_class", [BashActivator, CShellActivator, FishActivator, PowerShellActivator, PythonActivator]
)
def test_activator_support_posix(mocker, activator_class):
    activator = activator_class(SimpleNamespace(prompt=None))
    interpreter = mocker.Mock(spec=PythonInfo)
    interpreter.os = "posix"
    assert activator.supports(interpreter)


@pytest.mark.parametrize("activator_class", [DOSActivator])
def test_activator_no_support_posix(mocker, activator_class):
    activator = activator_class(SimpleNamespace(prompt=None))
    interpreter = mocker.Mock(spec=PythonInfo)
    interpreter.os = "posix"
    assert not activator.supports(interpreter)
