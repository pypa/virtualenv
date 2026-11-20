from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable


def user_dir(locate: Callable[[], str]) -> str | None:
    """Locate a per-user folder without accepting an unresolved home path.

    :param locate: the platformdirs lookup to run

    :returns: the folder, or ``None`` when the home directory cannot be found

    """
    try:
        folder = locate()
    except RuntimeError:
        return None
    return None if folder.startswith("~") else folder


__all__ = [
    "user_dir",
]
