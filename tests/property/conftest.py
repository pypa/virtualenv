from __future__ import annotations

from importlib.util import find_spec
from typing import Final

collect_ignore_glob: Final[list[str]] = [] if find_spec("hypothesis") else ["*.py"]
