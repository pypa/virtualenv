import os
import sys

# Windows detection, covers CPython and IronPython
WINDOWS = (
    sys.platform.startswith("win")
    or (sys.platform == "cli" and os.name == "nt")
)
