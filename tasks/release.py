from __future__ import annotations

import argparse
import sys
from pathlib import Path
from subprocess import check_call, run
from typing import Final

from git import Remote, Repo
from release_creator.contributors.section import add_new_contributors
from release_creator.fragments.git import fragment_commits_from_git
from release_creator.fragments.links import add_pull_request_links
from release_creator.fragments.names import pending_fragments
from release_creator.fragments.pull_requests import fragment_pull_requests
from release_creator.tags.select import next_tag


def main(bump: str, *, push: bool) -> None:
    root_src_dir: Final[Path] = Path(__file__).resolve().parents[1]
    changelog_dir: Final[Path] = root_src_dir / "docs" / "changelog"
    repo = Repo(str(root_src_dir))
    remote = get_remote(repo)
    remote.fetch()
    version = next_tag(
        bump,
        [tag.name for tag in repo.tags],
        [fragment.name for fragment in pending_fragments(changelog_dir)],
    )
    commits = fragment_commits_from_git(changelog_dir)
    pull_requests = fragment_pull_requests("pypa/virtualenv", {name: commit.sha for name, commit in commits.items()})
    add_pull_request_links(changelog_dir, "pypa/virtualenv", pull_requests, commits=commits)
    check_call([sys.executable, "-m", "towncrier", "build", "--yes", "--version", version], cwd=root_src_dir)
    add_new_contributors(root_src_dir / "docs" / "changelog.rst", version, "pypa/virtualenv")
    run(
        [sys.executable, "-m", "prek", "run", "docstrfmt", "--files", "docs/changelog.rst"],
        cwd=root_src_dir,
        check=False,
    )
    check_call([sys.executable, "-m", "prek", "run", "docstrfmt", "--files", "docs/changelog.rst"], cwd=root_src_dir)
    check_call([sys.executable, "-m", "prek", "run", "--all-files"], cwd=root_src_dir)
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
