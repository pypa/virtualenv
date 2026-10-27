from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Final

import pytest
from git import Repo
from release_creator.fragments.pull_requests import PullRequest, PullRequestCredit

from tasks import release

if TYPE_CHECKING:
    from pytest_mock import MockerFixture


@pytest.fixture
def release_checkout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mocker: MockerFixture) -> tuple[Repo, Repo, Path]:
    remote: Final[Repo] = Repo.init(tmp_path / "pypa" / "virtualenv", bare=True)
    repo: Final[Repo] = Repo.init(tmp_path / "checkout")
    root: Final[Path] = Path(repo.working_dir)
    unrelated: Final[Repo] = Repo.init(tmp_path / "elsewhere", bare=True)
    repo.create_remote("elsewhere", str(unrelated.git_dir))
    repo.create_remote("origin", str(remote.git_dir))
    with repo.config_writer() as config:
        config.set_value("user", "name", "Test")
        config.set_value("user", "email", "test@example.com")
    (root / "docs" / "changelog").mkdir(parents=True)
    (root / "docs" / "changelog" / "+release.bugfix.rst").write_text("Fix environment creation.\n", encoding="utf-8")
    (root / "pyproject.toml").write_text(
        '[tool.towncrier]\nname = "demo"\ndirectory = "docs/changelog"\nfilename = "docs/changelog.rst"\n'
        'template = "release_creator.fragments:template.rst.jinja2"\ntitle_format = false\n'
        'issue_format = ":pr:`{issue}`"\n[[tool.towncrier.type]]\n'
        'directory = "bugfix"\nname = "Fixed"\nshowcontent = true\n',
        encoding="utf-8",
    )
    (root / ".pre-commit-config.yaml").write_text(
        "repos:\n  - repo: local\n    hooks:\n      - id: docstrfmt\n        name: docstrfmt\n"
        "        entry: python -m docstrfmt -l 120 --preserve-adornments\n"
        "        language: system\n        files: ^docs/changelog[.]rst$\n",
        encoding="utf-8",
    )
    repo.git.add(".")
    repo.index.commit("Fix environment creation (#1)")
    repo.create_tag("1.2.2")
    repo.git.push("origin", "refs/tags/1.2.2")
    monkeypatch.chdir(root)
    mocker.patch.object(release, "__file__", str(root / "tasks" / "release.py"))
    mocker.patch.object(release, "add_new_contributors", autospec=True)
    mocker.patch.object(
        release,
        "fragment_pull_requests",
        return_value={
            "+release.bugfix.rst": PullRequest(
                number="1",
                credits=(PullRequestCredit(name="test-user", linked=True),),
            )
        },
    )
    return repo, remote, root


def test_release_prepares_tag_without_push(release_checkout: tuple[Repo, Repo, Path]) -> None:
    repo, remote, root = release_checkout
    release.main("auto", push=False)
    assert repo.tags["1.2.3"].commit == repo.head.commit
    assert "1.2.3" not in remote.tags
    assert "(:pr:`1`) by :user:`test-user`" in (root / "docs" / "changelog.rst").read_text(encoding="utf-8")


def test_release_adds_new_contributors_for_the_release(release_checkout: tuple[Repo, Repo, Path]) -> None:
    _, _, root = release_checkout
    release.main("auto", push=False)
    release.add_new_contributors.assert_called_once_with(root / "docs" / "changelog.rst", "1.2.3", "pypa/virtualenv")


def test_release_pushes_commit_and_tag_to_local_remote(release_checkout: tuple[Repo, Repo, Path]) -> None:
    repo, remote, _ = release_checkout
    release.main("auto", push=True)
    assert remote.tags["1.2.3"].commit == repo.head.commit
    assert remote.refs["main"].commit == repo.head.commit


def test_release_requires_upstream_remote(tmp_path: Path, mocker: MockerFixture) -> None:
    repo = Repo.init(tmp_path / "checkout")
    mocker.patch.object(release, "__file__", str(Path(repo.working_dir) / "tasks" / "release.py"))
    with pytest.raises(RuntimeError, match="pypa/virtualenv remote"):
        release.main("auto", push=False)


def test_release_cli_help() -> None:
    result = subprocess.run(
        [sys.executable, str(Path(release.__file__).resolve()), "--help"],
        capture_output=True,
        check=False,
        text=True,
        encoding="utf-8",
    )
    assert result.returncode == 0
    assert "--bump" in result.stdout
