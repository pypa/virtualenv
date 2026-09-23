from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Final
from urllib.request import Request, urlopen

_PINS: Final[Path] = Path("tasks/ci-tools.json")
_TOOLS: Final[dict[str, tuple[str, bool, dict[str, str]]]] = {
    "nushell": ("nushell/nushell", False, {"Windows": "nu-{version}-x86_64-pc-windows-msvc.zip"}),
    "rustpython": (
        "RustPython/RustPython",
        True,
        {
            "Linux": "rustpython-release-Linux-x86_64-unknown-linux-gnu",
            "macOS": "rustpython-release-macOS-aarch64-apple-darwin",
            "Windows": "rustpython-release-Windows-x86_64-pc-windows-msvc.exe",
        },
    ),
}
# the REST release listing of RustPython/RustPython comes back empty, so query GraphQL, which sees its releases
_QUERY: Final[str] = """
query($owner: String!, $name: String!) {
  repository(owner: $owner, name: $name) {
    latestRelease { tagName }
    releases(first: 1, orderBy: {field: CREATED_AT, direction: DESC}) { nodes { tagName } }
  }
}
"""


def main() -> None:
    if not (token := os.environ.get("GH_TOKEN")):
        msg = "GH_TOKEN is required to query GitHub releases"
        raise SystemExit(msg)
    pins: Final = json.loads(_PINS.read_text(encoding="utf-8"))
    for tool, (repository, prerelease, patterns) in _TOOLS.items():
        # an unchanged tag keeps its recorded hashes, so an asset replaced under the same tag fails CI instead
        if (tag := _newest_tag(token, repository, prerelease=prerelease)) != pins[tool]["tag"]:
            pins[tool] = {"tag": tag, "assets": _pin_assets(token, repository, tag, patterns)}
    _PINS.write_text(f"{json.dumps(pins, indent=2, sort_keys=True)}\n", encoding="utf-8")


def _newest_tag(token: str, repository: str, *, prerelease: bool) -> str:
    owner, name = repository.split("/")
    with urlopen(
        Request(
            "https://api.github.com/graphql",
            data=json.dumps({"query": _QUERY, "variables": {"owner": owner, "name": name}}).encode(),
            headers={"Authorization": f"Bearer {token}"},
        ),
        timeout=30,
    ) as response:
        found: Final = json.load(response)["data"]["repository"]
    return found["releases"]["nodes"][0]["tagName"] if prerelease else found["latestRelease"]["tagName"]


def _pin_assets(token: str, repository: str, tag: str, patterns: dict[str, str]) -> dict[str, dict[str, str]]:
    with urlopen(
        Request(
            f"https://api.github.com/repos/{repository}/releases/tags/{tag}",
            headers={"Authorization": f"Bearer {token}"},
        ),
        timeout=30,
    ) as response:
        published: Final = {asset["name"]: asset for asset in json.load(response)["assets"]}
    pins: Final[dict[str, dict[str, str]]] = {}
    for runner_os, pattern in patterns.items():
        if (asset := published.get(name := pattern.format(version=tag.removeprefix("v")))) is None:
            msg = f"{repository} {tag} has no asset {name}"
            raise SystemExit(msg)
        sha256 = _sha256(repository, asset["id"])
        if (digest := asset.get("digest")) and digest != f"sha256:{sha256}":
            msg = f"{name} hashes to {sha256} but GitHub reports {digest}"
            raise SystemExit(msg)
        pins[runner_os] = {"name": name, "sha256": sha256}
    return pins


def _sha256(repository: str, asset_id: int) -> str:
    digest: Final = hashlib.sha256()
    # no token: the API redirects to a signed storage URL, and urllib would forward the Authorization header there
    with urlopen(
        Request(
            f"https://api.github.com/repos/{repository}/releases/assets/{asset_id}",
            headers={"Accept": "application/octet-stream"},
        ),
        timeout=300,
    ) as response:
        for chunk in iter(lambda: response.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


__all__ = ["main"]


if __name__ == "__main__":
    main()
