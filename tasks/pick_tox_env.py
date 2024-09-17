from __future__ import annotations

import os
import sys
from pathlib import Path

py = sys.argv[1]
if py.startswith("brew@"):
    py = py[len("brew@") :]
env = f"TOXENV={py}"
with Path(os.environ["GITHUB_ENV"]).open("ta", encoding="utf-8") as file_handler:
    file_handler.write(env)
