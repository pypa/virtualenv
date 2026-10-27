from __future__ import annotations

import os
from typing import TYPE_CHECKING

from virtualenv.util.path import write_file

if TYPE_CHECKING:
    from pathlib import Path


def redirect_in_place(redirect: Path, name: str) -> None:
    redirect.write_text(f"{name}\n", encoding="utf-8")


def record_in_place(record: Path, data: bytes) -> None:
    with record.open("wb") as stream:
        stream.write(data)


def record_os_open(record: Path, data: bytes) -> None:
    with os.fdopen(os.open(record, os.O_WRONLY | os.O_CREAT, 0o644), "wb") as stream:
        stream.write(data)


def redirect_exclusive(redirect: Path, name: str) -> None:
    write_file(redirect, f"{name}\n".encode())


def record_exclusive(record: Path, data: bytes) -> None:
    with os.fdopen(os.open(record, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644), "wb") as stream:
        stream.write(data)
