"""Keep the property tests out of collection when hypothesis is absent.

The marker deselection in addopts runs after import, so without this the default test environments, which do not install
hypothesis, fail at collection rather than skipping.

"""

from __future__ import annotations

from importlib.util import find_spec

collect_ignore_glob = [] if find_spec("hypothesis") else ["*.py"]
