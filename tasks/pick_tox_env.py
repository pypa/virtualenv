from __future__ import annotations

import os
import sys
from pathlib import Path

py = sys.argv[1]
env_lines = []

if py.startswith("brew@"):
    brew_version = py[len("brew@") :]
    env_lines.append(f"TOX_DISCOVER=/opt/homebrew/bin/python{brew_version}")
    py = brew_version

if py.startswith("graalpy-"):
    py = "graalpy"

env_lines.append(f"TOXENV={py}")
env = "\n".join(env_lines) + "\n"

with Path(os.environ["GITHUB_ENV"]).open("a", encoding="utf-8") as file_handler:
    file_handler.write(env)

print(f"Written to GITHUB_ENV:\n{env}")
