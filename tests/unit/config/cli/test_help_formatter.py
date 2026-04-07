"""Tests for HelpFormatter terminal width behavior."""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from virtualenv.config.cli.parser import HelpFormatter


@pytest.mark.parametrize("width", [80, 120, 200])
def test_help_formatter_uses_terminal_width(width: int) -> None:
    """HelpFormatter should use shutil.get_terminal_size() for width."""
    with patch("virtualenv.config.cli.parser.shutil.get_terminal_size") as mock_size:
        mock_size.return_value = os.terminal_size((width, 24))
        formatter = HelpFormatter("test_prog")
        assert formatter._width == width  # noqa: SLF001


def test_help_formatter_not_hardcoded_240() -> None:
    """HelpFormatter width should not be hardcoded to 240."""
    with patch("virtualenv.config.cli.parser.shutil.get_terminal_size") as mock_size:
        mock_size.return_value = os.terminal_size((80, 24))
        formatter = HelpFormatter("test_prog")
        assert formatter._width != 240  # noqa: SLF001
