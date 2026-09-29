from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Final

from git import Repo


def test_release_without_tools_on_path(tmp_path: Path) -> None:
    remote: Final = Repo.init(tmp_path / "pypa" / "virtualenv", bare=True)
    repo: Final = Repo.init(tmp_path / "checkout")
    root: Final = Path(repo.working_dir)
    repo.create_remote("origin", str(remote.git_dir))
    with repo.config_writer() as config:
        config.set_value("user", "name", "Test")
        config.set_value("user", "email", "test@example.com")
    (root / "tasks").mkdir()
    shutil.copyfile(Path(__file__).parents[2] / "tasks" / "release.py", root / "tasks" / "release.py")
    (root / "docs" / "changelog").mkdir(parents=True)
    fragment: Final = "The release tools use the active interpreter. " * 6
    (root / "docs" / "changelog" / "1.bugfix.rst").write_text(fragment + "\n", encoding="utf-8")
    (root / "pyproject.toml").write_text(
        '[tool.towncrier]\nname = "demo"\ndirectory = "docs/changelog"\nfilename = "docs/changelog.rst"\n',
        encoding="utf-8",
    )
    repo.git.add(".")
    repo.index.commit("initial")
    git: Final = shutil.which("git")
    assert git is not None
    command_dir: Final = tmp_path / "bin"
    command_dir.mkdir()
    (command_dir / Path(git).name).symlink_to(git)
    result: Final = subprocess.run(
        [sys.executable, "tasks/release.py", "--version", "1.2.3", "--no-push"],
        cwd=root,
        env={**os.environ, "PATH": str(command_dir), "GIT_PYTHON_GIT_EXECUTABLE": git},
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    changelog: Final = (root / "docs" / "changelog.rst").read_text(encoding="utf-8")
    assert fragment.strip() in " ".join(changelog.split())
    assert max(map(len, changelog.splitlines())) <= 120
    assert repo.tags["1.2.3"].commit == repo.head.commit
    assert repo.head.commit.message == "release 1.2.3"
    assert not repo.is_dirty(untracked_files=True)
    assert not remote.tags
