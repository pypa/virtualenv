"""Check a wheel's or zipapp's SBOM with python-sbom and the license policy, and that a zipapp's SBOM matches it."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import zipfile
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final

from license_policy import ALLOWED_LICENSES

if TYPE_CHECKING:
    from collections.abc import Iterator

# python-sbom archive --embed writes it at the archive root, next to the zipapp's __main__.py
_ZIPAPP_SBOM: Final[str] = "virtualenv.pyz.cdx.json"
_Component = dict[str, Any]


def main() -> None:
    target = Path(sys.argv[1])
    artifacts = [target] if target.suffix == ".pyz" else sorted(target.glob("*.whl"))
    if len(artifacts) != 1:
        msg = f"expected exactly one wheel in {target}, found {len(artifacts)}: {[a.name for a in artifacts]}"
        raise SystemExit(msg)
    policy = [argument for spdx_id in sorted(ALLOWED_LICENSES) for argument in ("--allow-license", spdx_id)]
    command = [sys.executable, "-m", "python_sbom", "validate", str(artifacts[0]), *policy]
    if subprocess.run(command, check=False).returncode:
        raise SystemExit(1)
    if target.suffix == ".pyz" and (problems := describes_archive(target)):
        for problem in problems:
            # the validator prints each problem it found to the terminal
            print(f"SBOM invalid: {problem}")  # ruff:ignore[print]
        raise SystemExit(1)


def describes_archive(pyz: Path) -> list[str]:
    with zipfile.ZipFile(pyz) as archive:
        document = json.loads(archive.read(_ZIPAPP_SBOM))
        contents: Final[dict[str, str]] = {
            name: hashlib.sha256(archive.read(name)).hexdigest()
            for name in archive.namelist()
            if not name.endswith("/") and name != _ZIPAPP_SBOM
        }
    described: Final[dict[str, str]] = dict(
        _described_files([document["metadata"]["component"], *document["components"]])
    )
    problems: Final[list[str]] = []
    if missing := sorted(contents.keys() - described.keys()):
        problems.append(f"{pyz.name} holds files the SBOM does not describe: {missing}")
    if unknown := sorted(described.keys() - contents.keys()):
        problems.append(f"SBOM describes files {pyz.name} does not hold: {unknown}")
    if changed := sorted(name for name in contents.keys() & described.keys() if contents[name] != described[name]):
        problems.append(f"SHA-256 in the SBOM differs from the archive for: {changed}")
    return problems


def _described_files(components: list[_Component]) -> Iterator[tuple[str, str]]:
    for component in components:
        digest = next((entry["content"] for entry in component.get("hashes", []) if entry["alg"] == "SHA-256"), "")
        if component["type"] == "file":
            yield component["name"], digest
        # an embedded wheel is one archive member; the files nested under it are the wheel's own, not the zipapp's
        if component["bom-ref"].startswith("bundled:") and component["bom-ref"].endswith(".whl"):
            yield component["bom-ref"].removeprefix("bundled:"), digest
            continue
        yield from _described_files(component.get("components", []))


if __name__ == "__main__":
    main()
