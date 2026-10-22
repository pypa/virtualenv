"""Download a URL, retrying the failures a package index recovers from."""

from __future__ import annotations

import sys
import time
from http import HTTPStatus
from urllib.error import HTTPError, URLError
from urllib.request import urlopen


def fetch(url: str) -> bytes:
    # a dropped connection or a server error from the index is transient; a client error is not
    for delay in (2, 4):
        try:
            return _read(url)
        except (URLError, TimeoutError, ConnectionError) as exc:
            if isinstance(exc, HTTPError) and exc.code < HTTPStatus.INTERNAL_SERVER_ERROR:
                raise
            sys.stderr.write(f"{url}: {exc}, retrying in {delay}s\n")
        time.sleep(delay)
    return _read(url)


def _read(url: str) -> bytes:
    with urlopen(url, timeout=60) as response:  # ruff:ignore[suspicious-url-open-usage]  # callers hash-check the bytes
        return response.read()


__all__ = ["fetch"]
