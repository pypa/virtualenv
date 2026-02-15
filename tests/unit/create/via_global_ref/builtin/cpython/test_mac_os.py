from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING

from virtualenv.create.via_global_ref.builtin.cpython.mac_os import resign

if TYPE_CHECKING:
    from pytest_mock import MockerFixture


def test_resign_calls_codesign(mocker: MockerFixture) -> None:
    mock_check_call = mocker.patch("subprocess.check_call")
    resign("/path/to/exe")
    mock_check_call.assert_called_once_with(["codesign", "--force", "--sign", "-", "/path/to/exe"])


def test_resign_handles_os_error(mocker: MockerFixture) -> None:
    mocker.patch("subprocess.check_call", side_effect=OSError("not found"))
    resign("/path/to/exe")


def test_resign_handles_called_process_error(mocker: MockerFixture) -> None:
    mocker.patch(
        "subprocess.check_call",
        side_effect=subprocess.CalledProcessError(1, "codesign"),
    )
    resign("/path/to/exe")
