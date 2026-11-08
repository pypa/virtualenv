from __future__ import annotations

import os
import shutil
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable


def safe_delete(dest: str) -> None:
    def onerror(func: Callable[[str], object], path: str, _exc_info: object) -> None:
        os.chmod(path, 0o700)
        func(path)

    shutil.rmtree(dest, onerror=onerror)


def plain_delete(dest: str) -> None:
    def onerror(func: Callable[[str], object], path: str, _exc_info: object) -> None:
        func(path)

    shutil.rmtree(dest, onerror=onerror)
