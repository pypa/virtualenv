from __future__ import annotations

import json
import shutil
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Final
from urllib.request import urlopen


def main() -> None:
    cutoff: Final[datetime] = datetime.now(tz=timezone.utc) - timedelta(days=7)
    rejected: Final[list[str]] = []
    for wheel in _changed_wheels():
        package, version, *_ = wheel.name.split("-")
        with urlopen(f"https://pypi.org/pypi/{package}/{version}/json", timeout=30) as response:
            files = json.load(response)["urls"]
        if (artifact := next((file for file in files if file["filename"] == wheel.name), None)) is None:
            msg = f"PyPI has no upload information for {wheel.name}"
            raise SystemExit(msg)
        if datetime.fromisoformat(artifact["upload_time_iso_8601"].replace("Z", "+00:00")) > cutoff:
            rejected.append(wheel.name)
    if rejected:
        sys.stderr.write(f"Wheels uploaded less than seven days ago: {', '.join(rejected)}\n")
    sys.stdout.write(f"skip={'true' if rejected else 'false'}\n")


def _changed_wheels() -> list[Path]:
    if (git := shutil.which("git")) is None:
        msg = "git is required to find changed wheels"
        raise SystemExit(msg)
    paths: Final[set[str]] = set()
    for arguments in (
        ["diff", "--name-only", "--diff-filter=AM", "-z", "HEAD"],
        ["ls-files", "--others", "--exclude-standard", "-z"],
    ):
        result = subprocess.run(
            [git, *arguments, "--", "src/virtualenv/seed/wheels/embed/*.whl"],
            check=True,
            capture_output=True,
            encoding="utf-8",
        )
        paths.update(result.stdout.rstrip("\0").split("\0"))
    return [Path(path) for path in sorted(paths) if path]


__all__ = ["main"]


if __name__ == "__main__":
    main()
