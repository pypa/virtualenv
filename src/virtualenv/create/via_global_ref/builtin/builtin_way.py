from __future__ import annotations

from abc import ABCMeta

from virtualenv.create.creator import Creator
from virtualenv.create.describe import Describe


class VirtualenvBuiltin(Creator, Describe, metaclass=ABCMeta):
    """A creator that does operations itself without delegation, if we can create it we can also describe it."""

    def __init__(self, options, interpreter) -> None:
        Creator.__init__(self, options, interpreter)  # noqa: PLC2801
        Describe.__init__(self, self.dest, interpreter)  # noqa: PLC2801


__all__ = [
    "VirtualenvBuiltin",
]
