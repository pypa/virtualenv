from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import PurePosixPath
from typing import Final


def main() -> None:
    if (git := shutil.which("git")) is None:
        msg = "git is required to apply an upgrade patch"
        raise SystemExit(msg)
    subprocess.run([git, "diff", "--cached", "--exit-code"], check=True)
    subprocess.run([git, "apply", "--check", sys.argv[1]], check=True)
    subprocess.run([git, "apply", "--cached", sys.argv[1]], check=True)
    changes: Final = (
        subprocess
        .run(
            [git, "diff", "--cached", "--raw", "--no-renames", "-z"],
            check=True,
            capture_output=True,
            encoding="utf-8",
        )
        .stdout.rstrip("\0")
        .split("\0")
    )
    for header, filename in zip(changes[::2], changes[1::2]):
        path: Final[PurePosixPath] = PurePosixPath(filename)
        allowed: Final[bool] = filename in {
            "THIRD-PARTY-NOTICES.md",
            "docs/changelog/u.bugfix.rst",
            "tasks/ci-tools.json",
        } or (
            path.parent == PurePosixPath("src/virtualenv/seed/wheels/embed")
            and (path.name == "__init__.py" or path.suffix == ".whl")
        )
        if not allowed or header.split()[1] not in {"100644", "000000"}:
            msg = f"Upgrade patch contains an unsupported path or file mode: {filename}"
            raise SystemExit(msg)
    subprocess.run([git, "apply", sys.argv[1]], check=True)


__all__ = ["main"]


if __name__ == "__main__":
    main()
