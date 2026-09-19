from __future__ import annotations

import ast
import json
import tempfile
import uuid
from pathlib import Path
from typing import Any, Final

from hatchling.builders.hooks.plugin.interface import BuildHookInterface

_ROOT: Final[Path] = Path(__file__).resolve().parent
_EMBED_INIT: Final[Path] = _ROOT / "src" / "virtualenv" / "seed" / "wheels" / "embed" / "__init__.py"
_SBOM_NAMESPACE: Final[uuid.UUID] = uuid.uuid5(uuid.NAMESPACE_URL, "https://github.com/pypa/virtualenv/sboms")


class SbomBuildHook(BuildHookInterface):
    """Write a PEP 770 CycloneDX SBOM into the wheel's ``.dist-info/sboms/`` directory.

    General-purpose SBOM scanners (syft, cyclonedx-py, GitHub's dependency graph) read declared dependency metadata or
    an installed environment, and virtualenv's bundled pip and setuptools wheels are neither: they are data files
    embedded under ``src/virtualenv/seed/wheels/embed/``, invisible to every one of those tools. Declaring them here,
    read straight out of the ``BUNDLE_SUPPORT``/``BUNDLE_SHA256`` tables that ``tasks/upgrade_wheels.py`` already
    maintains, means the SBOM tracks a wheel bump automatically instead of needing its own update step.

    """

    PLUGIN_NAME = "sbom"

    def initialize(self, version: str, build_data: dict[str, Any]) -> None:  # ruff:ignore[unused-method-argument]
        # `version` here is hatchling's build variant name (e.g. "standard"), not the package version
        if self.target_name != "wheel" or "sbom_files" not in build_data:
            # sbom_files only exists on hatchling>=1.28, which build-system.requires excludes for the
            # Python versions old enough to still need hatchling<1.28 for building at all
            return
        document = _cyclonedx_document(self.metadata.version, self.metadata.core.name)
        # written outside self.directory, which hatchling also uses as the final wheel output location, so a
        # stray copy here would sit next to the built artifacts and trip `twine check dist/*`
        out = Path(tempfile.mkdtemp(prefix="virtualenv-sbom-")) / "virtualenv.cdx.json"
        out.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
        build_data["sbom_files"].append(str(out))


def _cyclonedx_document(version: str, name: str) -> dict[str, Any]:
    wheel_sha256 = _bundled_wheels()
    components = []
    dependencies = [{"ref": f"pkg:pypi/{name}@{version}", "dependsOn": []}]
    for filename, sha256 in sorted(wheel_sha256.items()):
        distribution, wheel_version = filename.split("-")[:2]
        purl = f"pkg:pypi/{distribution}@{wheel_version}"
        components.append({
            "type": "library",
            "name": distribution,
            "version": wheel_version,
            "purl": purl,
            "bom-ref": purl,
            "licenses": [{"license": {"id": "MIT"}}],
            "hashes": [{"alg": "SHA-256", "content": sha256}],
            "externalReferences": [
                {"type": "distribution", "url": f"https://pypi.org/project/{distribution}/{wheel_version}/"},
            ],
            "properties": [
                {"name": "virtualenv:bundled-wheel", "value": f"src/virtualenv/seed/wheels/embed/{filename}"},
            ],
        })
        dependencies[0]["dependsOn"].append(purl)
        dependencies.append({"ref": purl, "dependsOn": []})
    return {
        "bomFormat": "CycloneDX",
        "specVersion": "1.6",
        "serialNumber": _serial_number(name, version, wheel_sha256),
        "version": 1,
        "metadata": {
            "component": {
                "type": "application",
                "name": name,
                "version": version,
                "purl": f"pkg:pypi/{name}@{version}",
                "bom-ref": f"pkg:pypi/{name}@{version}",
            },
        },
        "components": components,
        "dependencies": dependencies,
    }


def _bundled_wheels() -> dict[str, str]:
    tree = ast.parse(_EMBED_INIT.read_text(encoding="utf-8"))
    sha256_by_name = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "BUNDLE_SHA256" for target in node.targets
        ):
            sha256_by_name = ast.literal_eval(node.value)
            break
    if not sha256_by_name:
        msg = f"BUNDLE_SHA256 not found in {_EMBED_INIT}"
        raise RuntimeError(msg)
    return sha256_by_name


def _serial_number(name: str, version: str, wheel_sha256: dict[str, str]) -> str:
    # uuid5 rather than uuid4: deterministic on the inputs that actually change the SBOM's content, so two builds
    # of the same commit against the same bundled wheels produce a byte-identical document
    payload = f"{name}@{version}+{','.join(f'{k}:{v}' for k, v in sorted(wheel_sha256.items()))}"
    return f"urn:uuid:{uuid.uuid5(_SBOM_NAMESPACE, payload)}"
