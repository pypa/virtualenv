"""Render the CycloneDX SBOM that hatch_build.py embeds in the wheel as an SPDX 2.3 JSON document."""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final

if TYPE_CHECKING:
    from collections.abc import Iterator

_REPOSITORY: Final[str] = "https://github.com/pypa/virtualenv"
_PURPOSES: Final[dict[str, str]] = {
    "application": "APPLICATION",
    "library": "LIBRARY",
    "operating-system": "OPERATING-SYSTEM",
    "platform": "OTHER",
}


def main() -> None:
    source, target = map(Path, sys.argv[1:3])
    document: Final[dict[str, Any]] = to_spdx(json.loads(source.read_text(encoding="utf-8")))
    target.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")


def to_spdx(bom: dict[str, Any]) -> dict[str, Any]:
    root: Final[dict[str, Any]] = bom["metadata"]["component"]
    tools: Final[list[dict[str, Any]]] = bom["metadata"]["tools"]["components"]
    name: Final[str] = f"{root['name']}-{root['version']}"
    components: Final[list[dict[str, Any]]] = list(_walk([root, *bom["components"], *tools]))
    created: Final[datetime] = datetime.fromisoformat(bom["metadata"]["timestamp"]).astimezone(timezone.utc)
    return {
        "spdxVersion": "SPDX-2.3",
        "dataLicense": "CC0-1.0",
        "SPDXID": "SPDXRef-DOCUMENT",
        "name": name,
        # the CycloneDX serial is derived from its content, so the namespace stays stable across rebuilds
        "documentNamespace": f"{_REPOSITORY}/sboms/{name}-{bom['serialNumber'].removeprefix('urn:uuid:')}",
        "comment": f"Rendered from the CycloneDX SBOM {bom['serialNumber']} (virtualenv.cdx.json), which also carries"
        " per-file hashes and the build formulation.",
        "creationInfo": {
            "created": created.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "creators": [
                f"Organization: {bom['metadata']['supplier']['name']}",
                *(f"Tool: {tool['name']}-{tool['version']}" for tool in tools if tool["type"] == "application"),
                f"Tool: {Path(__file__).name}-{root['version']}",
            ],
        },
        "packages": [_package(component) for component in components],
        "relationships": [
            _relationship("SPDXRef-DOCUMENT", "DESCRIBES", _spdx_id(root["bom-ref"])),
            *(
                _relationship(_spdx_id(parent["bom-ref"]), "CONTAINS", _spdx_id(child["bom-ref"]))
                for parent in components
                for child in parent.get("components", [])
                if child["type"] != "file"
            ),
            *(
                _relationship(_spdx_id(entry["ref"]), "DEPENDS_ON", _spdx_id(dependency))
                for entry in bom["dependencies"]
                for dependency in entry.get("dependsOn", [])
            ),
            *(_relationship(_spdx_id(tool["bom-ref"]), "BUILD_TOOL_OF", _spdx_id(root["bom-ref"])) for tool in tools),
        ],
    }


def _walk(components: list[dict[str, Any]]) -> Iterator[dict[str, Any]]:
    # file components mirror the wheels' RECORD entries, which carry no SHA-1 and so cannot become SPDX files
    for component in components:
        if component["type"] != "file":
            yield component
            yield from _walk(component.get("components", []))


def _package(component: dict[str, Any]) -> dict[str, Any]:
    package: Final[dict[str, Any]] = {
        "SPDXID": _spdx_id(component["bom-ref"]),
        "name": component["name"],
        "downloadLocation": "NOASSERTION",
        "filesAnalyzed": False,
        "licenseConcluded": "NOASSERTION",
        "licenseDeclared": "NOASSERTION",
        "primaryPackagePurpose": _PURPOSES[component["type"]],
    }
    references: Final[list[dict[str, str]]] = component.get("externalReferences", [])
    optional: Final[dict[str, Any]] = {
        "versionInfo": component.get("version"),
        "supplier": f"Organization: {supplier['name']}" if (supplier := component.get("supplier")) else None,
        "checksums": [
            {"algorithm": entry["alg"].replace("-", ""), "checksumValue": entry["content"]}
            for entry in component.get("hashes", [])
        ],
        "homepage": next((reference["url"] for reference in references if reference["type"] == "website"), None),
        "copyrightText": component.get("copyright"),
        "summary": component.get("description"),
        "comment": "\n".join(
            f"{prop['name']}: {prop['value']}"
            for prop in component.get("properties", [])
            if prop["name"].startswith("virtualenv:")
        ),
        "externalRefs": [{"referenceCategory": "PACKAGE-MANAGER", "referenceType": "purl", "referenceLocator": purl}]
        if (purl := component.get("purl"))
        else [],
    }
    package.update({key: value for key, value in optional.items() if value})
    # hatch_build.py emits either one SPDX expression or the free-form names from License/classifier metadata
    licenses: Final[list[dict[str, Any]]] = component.get("licenses", [])
    if expression := next((entry["expression"] for entry in licenses if "expression" in entry), None):
        package["licenseDeclared"] = expression
    elif names := [entry["license"]["name"] for entry in licenses]:
        package["licenseComments"] = f"Declared in package metadata as: {'; '.join(names)}"
    return package


def _relationship(element: str, kind: str, related: str) -> dict[str, str]:
    return {"spdxElementId": element, "relationshipType": kind, "relatedSpdxElement": related}


def _spdx_id(bom_ref: str) -> str:
    return f"SPDXRef-{re.sub(r'[^A-Za-z0-9.]+', '-', bom_ref).strip('-')}"


if __name__ == "__main__":
    main()
