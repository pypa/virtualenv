"""Prepare a local release from merged changelog fragments."""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path
from subprocess import check_call, run
from typing import Final

from git import Remote, Repo
from release_creator.fragments.git import commit_subjects_from_git
from release_creator.fragments.links import add_pull_request_links
from release_creator.fragments.names import pending_fragments
from release_creator.fragments.pull_requests import pull_request_authors
from release_creator.tags.select import next_tag

ROOT_SRC_DIR: Final[Path] = Path(__file__).resolve().parents[1]
CHANGELOG_DIR: Final[Path] = ROOT_SRC_DIR / "docs" / "changelog"


def main(bump: str, *, push: bool) -> None:
    repo = Repo(str(ROOT_SRC_DIR))
    if repo.is_dirty(untracked_files=True):
        msg = "Current repository is dirty. Commit or discard changes before preparing a release."
        raise RuntimeError(msg)
    remote = get_remote(repo)
    remote.fetch()
    version = next_tag(
        bump,
        [tag.name for tag in repo.tags],
        [fragment.name for fragment in pending_fragments(CHANGELOG_DIR)],
        datetime.now(UTC).date(),
    )
    subjects = commit_subjects_from_git(CHANGELOG_DIR)
    add_pull_request_links(
        CHANGELOG_DIR, "pypa/virtualenv", subjects, pull_request_authors("pypa/virtualenv", subjects)
    )
    check_call([sys.executable, "-m", "towncrier", "build", "--yes", "--version", version], cwd=ROOT_SRC_DIR)
    run(
        [sys.executable, "-m", "prek", "run", "docstrfmt", "--files", "docs/changelog.rst"],
        cwd=ROOT_SRC_DIR,
        check=False,
    )
    check_call([sys.executable, "-m", "prek", "run", "docstrfmt", "--files", "docs/changelog.rst"], cwd=ROOT_SRC_DIR)
    check_call([sys.executable, "-m", "prek", "run", "--all-files"], cwd=ROOT_SRC_DIR)
    repo.git.add("-A", "--", "docs")
    repo.index.commit(f"release {version}")
    repo.create_tag(version)
    if push:
        repo.git.push("--atomic", remote.name, "HEAD:main", f"refs/tags/{version}")
    sys.stdout.write(f"Prepared {version}\n")


def get_remote(repo: Repo) -> Remote:
    for remote in repo.remotes:
        if any(url.removesuffix(".git").endswith("pypa/virtualenv") for url in remote.urls):
            return remote
    msg = "could not find a pypa/virtualenv remote"
    raise RuntimeError(msg)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog="release")
    parser.add_argument("--bump", choices=("auto", "major", "minor", "patch"), default="auto")
    parser.add_argument("--no-push", action="store_true")
    options = parser.parse_args()
    main(options.bump, push=not options.no_push)


__all__ = [
    "main",
]
