from __future__ import annotations

import os
from typing import TYPE_CHECKING

import pytest

from virtualenv.config.cli.parser import HelpFormatter

if TYPE_CHECKING:
    from pytest_mock import MockerFixture


@pytest.mark.parametrize("width", [80, 120, 200])
def test_help_formatter_uses_terminal_width(mocker: MockerFixture, width: int) -> None:
    # HelpFormatter should use shutil.get_terminal_size() for width.
    mock_size = mocker.patch(
        "virtualenv.config.cli.parser.shutil.get_terminal_size",
        autospec=True,
        return_value=os.terminal_size((width, 24)),
    )
    formatter = HelpFormatter("test_prog")
    # argparse keeps the formatter width in _width, which the test checks
    assert formatter._width == width  # ruff:ignore[private-member-access]
    mock_size.assert_called()


def test_help_formatter_not_hardcoded_240(mocker: MockerFixture) -> None:
    # HelpFormatter width should not be hardcoded to 240.
    mocker.patch(
        "virtualenv.config.cli.parser.shutil.get_terminal_size", autospec=True, return_value=os.terminal_size((80, 24))
    )
    formatter = HelpFormatter("test_prog")
    # argparse keeps the formatter width in _width, which the test checks
    assert formatter._width != 240  # ruff:ignore[private-member-access]
