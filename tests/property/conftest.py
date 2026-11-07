from __future__ import annotations

from importlib.util import find_spec

collect_ignore_glob = [] if find_spec("hypothesis") else ["*.py"]
