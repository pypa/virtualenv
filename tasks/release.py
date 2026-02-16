"""Handles creating a release."""

from __future__ import annotations

from pathlib import Path
from subprocess import check_call

from git import Commit, Remote, Repo, TagReference
from packaging.version import Version

ROOT_SRC_DIR = Path(__file__).resolve().parents[1]
CHANGELOG_DIR = ROOT_SRC_DIR / "docs" / "changelog"


def main(version_str: str, *, push: bool) -> None:
    repo = Repo(str(ROOT_SRC_DIR))
    if repo.is_dirty():
        msg = "Current repository is dirty. Please commit any changes and try again."
        raise RuntimeError(msg)
    remote = get_remote(repo)
    remote.fetch()
    version = resolve_version(version_str, repo)
    print(f"releasing {version}")  # noqa: T201
    release_commit = release_changelog(repo, version)
    tag = tag_release_commit(release_commit, repo, version)
    if push:
        print("push release commit")  # noqa: T201
        repo.git.push(remote.name, "HEAD:main")
        print("push release tag")  # noqa: T201
        repo.git.push(remote.name, tag)
    print("All done! ✨ 🍰 ✨")  # noqa: T201


def resolve_version(version_str: str, repo: Repo) -> Version:
    if version_str not in {"auto", "major", "minor", "patch"}:
        return Version(version_str)
    latest_tag = repo.git.describe("--tags", "--abbrev=0")
    parts = [int(x) for x in latest_tag.split(".")]
    if version_str == "major":
        parts = [parts[0] + 1, 0, 0]
    elif version_str == "minor":
        parts = [parts[0], parts[1] + 1, 0]
    elif version_str == "patch":
        parts[2] += 1
    elif any(CHANGELOG_DIR.glob("*.feature.rst")) or any(CHANGELOG_DIR.glob("*.removal.rst")):
        parts = [parts[0], parts[1] + 1, 0]
    else:
        parts[2] += 1
    return Version(".".join(str(p) for p in parts))


def get_remote(repo: Repo) -> Remote:
    upstream_remote = "pypa/virtualenv"
    urls = set()
    for remote in repo.remotes:
        for url in remote.urls:
            if url.rstrip(".git").endswith(upstream_remote):
                return remote
            urls.add(url)
    msg = f"could not find {upstream_remote} remote, has {urls}"
    raise RuntimeError(msg)


def release_changelog(repo: Repo, version: Version) -> Commit:
    print("generate release commit")  # noqa: T201
    check_call(["towncrier", "build", "--yes", "--version", version.public], cwd=str(ROOT_SRC_DIR))  # noqa: S607
    repo.git.add(".")
    return repo.index.commit(f"release {version}")


def tag_release_commit(release_commit: Commit, repo: Repo, version: Version) -> TagReference:
    print("tag release commit")  # noqa: T201
    existing_tags = [x.name for x in repo.tags]
    if version in existing_tags:
        print(f"delete existing tag {version}")  # noqa: T201
        repo.delete_tag(version)
    print(f"create tag {version}")  # noqa: T201
    return repo.create_tag(version, ref=release_commit, force=True)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(prog="release")
    parser.add_argument("--version", default="auto")
    parser.add_argument("--no-push", action="store_true")
    options = parser.parse_args()
    main(options.version, push=not options.no_push)
