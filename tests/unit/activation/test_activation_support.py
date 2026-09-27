from __future__ import annotations

from argparse import Namespace
from typing import TYPE_CHECKING, Final

import pytest
from python_discovery import PythonInfo

from virtualenv.activation import (
    BashActivator,
    BatchActivator,
    CShellActivator,
    FishActivator,
    PowerShellActivator,
    PythonActivator,
    XonshActivator,
)

if TYPE_CHECKING:
    from virtualenv.activation.activator import Activator

_SUPPORTED_OS: Final[dict[type[Activator], set[str]]] = {
    BashActivator: {"nt", "posix"},
    BatchActivator: {"nt"},
    CShellActivator: {"posix"},
    FishActivator: {"nt", "posix"},
    PowerShellActivator: {"nt", "posix"},
    PythonActivator: {"nt", "posix"},
    XonshActivator: {"nt", "posix"},
}


@pytest.mark.parametrize(
    ("activator_class", "os_name"),
    [
        pytest.param(activator, os_name, id=f"{activator.__name__}-{os_name}")
        for activator in _SUPPORTED_OS
        for os_name in ("nt", "posix")
    ],
)
def test_activator_support(mocker, activator_class: type[Activator], os_name: str) -> None:
    activator = activator_class(Namespace(prompt=None))
    interpreter = mocker.Mock(spec=PythonInfo)
    interpreter.os = os_name
    assert activator.supports(interpreter) is (os_name in _SUPPORTED_OS[activator_class])
