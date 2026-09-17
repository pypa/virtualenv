"""Shared helpers for the fuzz targets in this directory."""

from __future__ import annotations

import atheris


def consume_text(data: bytes) -> str:
    provider = atheris.FuzzedDataProvider(data)
    return provider.ConsumeUnicodeNoSurrogates(provider.remaining_bytes())
