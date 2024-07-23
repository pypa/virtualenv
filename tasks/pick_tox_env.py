from __future__ import annotations

import os
import sys
from pathlib import Path

py = sys.argv[1]
if py.startswith("brew@"):
    py = py[len("brew@") :]
if py.startswith("graalpy-"):
    py = "graalpy"
env = f"TOXENV={py}"
if len(sys.argv) > 2:  # noqa: PLR2004
    env += f"\nTOX_BASEPYTHON={sys.argv[2]}"
with Path(os.environ["GITHUB_ENV"]).open("ta", encoding="utf-8") as file_handler:
    file_handler.write(env)
