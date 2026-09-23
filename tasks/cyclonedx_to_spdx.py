"""Render the CycloneDX SBOM that hatch_build.py embeds in the wheel as an SPDX 2.3 JSON document."""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from collections.abc import Iterator
    from typing import NotRequired, TypedDict

    class _Hash(TypedDict):
        alg: str
        content: str

    class _Reference(TypedDict):
        type: str
        url: str

    class _Property(TypedDict):
        name: str
        value: str

    class _Named(TypedDict):
        name: str

    class _License(TypedDict):
        expression: NotRequired[str]
        license: NotRequired[_Named]

    _Component = TypedDict(
        "_Component",
        {
            "type": str,
            "bom-ref": str,
            "name": str,
            "version": NotRequired[str],
            "purl": NotRequired[str],
            "supplier": NotRequired[_Named],
            "hashes": NotRequired[list[_Hash]],
            "externalReferences": NotRequired[list[_Reference]],
            "copyright": NotRequired[str],
            "description": NotRequired[str],
            "properties": NotRequired[list[_Property]],
            "licenses": NotRequired[list[_License]],
            "components": NotRequired[list["_Component"]],
        },
    )

    class _Tools(TypedDict):
        components: list[_Component]

    class _Metadata(TypedDict):
        timestamp: str
        supplier: _Named
        component: _Component
        tools: _Tools

    class _Dependency(TypedDict):
        ref: str
        dependsOn: NotRequired[list[str]]

    class CycloneDX(TypedDict):
        serialNumber: str
        metadata: _Metadata
        components: list[_Component]
        dependencies: list[_Dependency]

    class _Checksum(TypedDict):
        algorithm: str
        checksumValue: str

    class _ExternalRef(TypedDict):
        referenceCategory: str
        referenceType: str
        referenceLocator: str

    class _Package(TypedDict):
        SPDXID: str
        name: str
        downloadLocation: str
        filesAnalyzed: bool
        licenseConcluded: str
        licenseDeclared: str
        primaryPackagePurpose: str
        versionInfo: NotRequired[str]
        supplier: NotRequired[str]
        checksums: NotRequired[list[_Checksum]]
        homepage: NotRequired[str]
        copyrightText: NotRequired[str]
        summary: NotRequired[str]
        comment: NotRequired[str]
        externalRefs: NotRequired[list[_ExternalRef]]
        licenseComments: NotRequired[str]

    class _Relationship(TypedDict):
        spdxElementId: str
        relationshipType: str
        relatedSpdxElement: str

    class _CreationInfo(TypedDict):
        created: str
        creators: list[str]

    class Spdx(TypedDict):
        spdxVersion: str
        dataLicense: str
        SPDXID: str
        name: str
        documentNamespace: str
        comment: str
        creationInfo: _CreationInfo
        packages: list[_Package]
        relationships: list[_Relationship]


_REPOSITORY: Final[str] = "https://github.com/pypa/virtualenv"
_PURPOSES: Final[dict[str, str]] = {
    "application": "APPLICATION",
    "library": "LIBRARY",
    "platform": "OTHER",
}


def main() -> None:
    source, target = map(Path, sys.argv[1:3])
    bom: Final[CycloneDX] = json.loads(source.read_text(encoding="utf-8"))
    target.write_text(json.dumps(to_spdx(bom), indent=2) + "\n", encoding="utf-8")


def to_spdx(bom: CycloneDX) -> Spdx:
    root: Final[_Component] = bom["metadata"]["component"]
    tools: Final[list[_Component]] = bom["metadata"]["tools"]["components"]
    name: Final[str] = f"{root['name']}-{root['version']}"
    components: Final[list[_Component]] = list(_walk([root, *bom["components"], *tools]))
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
            "created": datetime
            .fromisoformat(bom["metadata"]["timestamp"])
            .astimezone(timezone.utc)
            .strftime("%Y-%m-%dT%H:%M:%SZ"),
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


def _walk(components: list[_Component]) -> Iterator[_Component]:
    # file components mirror the wheels' RECORD entries, which carry no SHA-1 and so cannot become SPDX files
    for component in components:
        if component["type"] != "file":
            yield component
            yield from _walk(component.get("components", []))


def _package(component: _Component) -> _Package:
    # hatch_build.py emits either one SPDX expression or the free-form names from License/classifier metadata
    licenses: Final[list[_License]] = component.get("licenses", [])
    package: Final[_Package] = {
        "SPDXID": _spdx_id(component["bom-ref"]),
        "name": component["name"],
        "downloadLocation": "NOASSERTION",
        "filesAnalyzed": False,
        "licenseConcluded": "NOASSERTION",
        "licenseDeclared": next((entry["expression"] for entry in licenses if "expression" in entry), "NOASSERTION"),
        "primaryPackagePurpose": _PURPOSES[component["type"]],
    }
    if version := component.get("version"):
        package["versionInfo"] = version
    if supplier := component.get("supplier"):
        package["supplier"] = f"Organization: {supplier['name']}"
    if hashes := component.get("hashes"):
        package["checksums"] = [
            {"algorithm": entry["alg"].replace("-", ""), "checksumValue": entry["content"]} for entry in hashes
        ]
    references: Final[list[_Reference]] = component.get("externalReferences", [])
    if homepage := next((reference["url"] for reference in references if reference["type"] == "website"), None):
        package["homepage"] = homepage
    if copyright_text := component.get("copyright"):
        package["copyrightText"] = copyright_text
    if description := component.get("description"):
        package["summary"] = description
    if comment := "\n".join(
        f"{prop['name']}: {prop['value']}"
        for prop in component.get("properties", [])
        if prop["name"].startswith("virtualenv:")
    ):
        package["comment"] = comment
    if purl := component.get("purl"):
        package["externalRefs"] = [
            {"referenceCategory": "PACKAGE-MANAGER", "referenceType": "purl", "referenceLocator": purl}
        ]
    if package["licenseDeclared"] == "NOASSERTION" and (
        names := [entry["license"]["name"] for entry in licenses if "license" in entry]
    ):
        package["licenseComments"] = f"Declared in package metadata as: {'; '.join(names)}"
    return package


def _relationship(element: str, kind: str, related: str) -> _Relationship:
    return {"spdxElementId": element, "relationshipType": kind, "relatedSpdxElement": related}


def _spdx_id(bom_ref: str) -> str:
    return f"SPDXRef-{re.sub(r'[^A-Za-z0-9.]+', '-', bom_ref).strip('-')}"


__all__ = [
    "CycloneDX",
    "to_spdx",
]


if __name__ == "__main__":
    main()
