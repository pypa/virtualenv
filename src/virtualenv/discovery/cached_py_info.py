"""Backward-compatibility re-export — use ``python_discovery`` directly."""

from __future__ import annotations

from python_discovery._cached_py_info import clear, from_exe  # noqa: PLC2701

__all__ = [
    "clear",
    "from_exe",
]
