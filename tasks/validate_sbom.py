"""Check that the SBOM embedded in a built wheel or zipapp is valid CycloneDX 1.6 and satisfies actions/attest."""

from __future__ import annotations

import hashlib
import json
import re
import sys
import zipfile
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final

from cyclonedx.schema import SchemaVersion
from cyclonedx.validation.json import JsonStrictValidator
from cyclonedx_to_spdx import to_spdx
from spdx_tools.spdx.parser.error import SPDXParsingError
from spdx_tools.spdx.parser.jsonlikedict.json_like_dict_parser import JsonLikeDictParser
from spdx_tools.spdx.validation.document_validator import validate_full_spdx_document

if TYPE_CHECKING:
    from collections.abc import Iterator
    from typing import NotRequired, TypedDict

    class _Hash(TypedDict):
        alg: str
        content: str

    class _Property(TypedDict):
        name: str
        value: str

    class _Component(TypedDict):
        type: str
        name: str
        hashes: NotRequired[list[_Hash]]
        properties: NotRequired[list[_Property]]
        components: NotRequired[list[_Component]]


_SERIAL_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"""
    ^urn:uuid:
    (?P<time_low>[0-9a-f]{8})-
    (?P<time_mid>[0-9a-f]{4})-
    (?P<time_high_and_version>[0-9a-f]{4})-
    (?P<clock_seq>[0-9a-f]{4})-
    (?P<node>[0-9a-f]{12})
    $
    """,
    re.VERBOSE,
)
# tasks/zipapp_sbom.py writes it at the archive root, next to the zipapp's __main__.py
_ZIPAPP_SBOM: Final[str] = "virtualenv.pyz.cdx.json"


def main() -> None:
    target = Path(sys.argv[1])
    if target.suffix == ".pyz":
        artifact, problems = target, validate_zipapp(target)
    else:
        wheels = sorted(target.glob("*.whl"))
        if len(wheels) != 1:
            msg = f"expected exactly one wheel in {target}, found {len(wheels)}: {[w.name for w in wheels]}"
            raise SystemExit(msg)
        artifact, problems = wheels[0], validate(wheels[0])
    if problems:
        for problem in problems:
            print(f"SBOM invalid: {problem}")  # ruff:ignore[print]
        raise SystemExit(1)
    print(f"SBOM in {artifact.name} is valid")  # ruff:ignore[print]


def validate(wheel: Path) -> list[str]:
    with zipfile.ZipFile(wheel) as archive:
        sbom_name = next((n for n in archive.namelist() if n.endswith("/sboms/virtualenv.cdx.json")), None)
        if sbom_name is None:
            return ["no .dist-info/sboms/virtualenv.cdx.json found in the wheel"]
        raw = archive.read(sbom_name).decode("utf-8")

    if schema_error := JsonStrictValidator(SchemaVersion.V1_6).validate_str(raw):
        return [f"does not conform to the CycloneDX 1.6 schema: {schema_error}"]
    document = json.loads(raw)

    problems = _validate_serial(document.get("serialNumber", ""))
    problems += _validate_references(document)
    problems += _validate_spdx(document)
    return problems


def validate_zipapp(pyz: Path) -> list[str]:
    with zipfile.ZipFile(pyz) as archive:
        if _ZIPAPP_SBOM not in archive.namelist():
            return [f"no {_ZIPAPP_SBOM} found in {pyz.name}"]
        raw = archive.read(_ZIPAPP_SBOM).decode("utf-8")
        contents: Final[dict[str, str]] = {
            name: hashlib.sha256(archive.read(name)).hexdigest()
            for name in archive.namelist()
            if not name.endswith("/") and name != _ZIPAPP_SBOM
        }
    if schema_error := JsonStrictValidator(SchemaVersion.V1_6).validate_str(raw):
        return [f"does not conform to the CycloneDX 1.6 schema: {schema_error}"]
    document = json.loads(raw)
    problems = _validate_serial(document.get("serialNumber", ""))
    problems += _validate_references(document)
    described: Final[dict[str, str]] = dict(
        _described_files([document["metadata"]["component"], *document["components"]])
    )
    if missing := sorted(contents.keys() - described.keys()):
        problems.append(f"{pyz.name} holds files the SBOM does not describe: {missing}")
    if unknown := sorted(described.keys() - contents.keys()):
        problems.append(f"SBOM describes files {pyz.name} does not hold: {unknown}")
    if changed := sorted(name for name in contents.keys() & described.keys() if contents[name] != described[name]):
        problems.append(f"SHA-256 in the SBOM differs from the archive for: {changed}")
    return problems


def _validate_serial(serial: str) -> list[str]:
    # optional in the CycloneDX spec itself, but actions/attest's format sniffer requires it to recognize
    # the document as CycloneDX at all, and silently rejects anything missing it as an unknown format
    return [] if _SERIAL_PATTERN.match(serial) else [f"serialNumber must be a urn:uuid: RFC 4122 UUID, got {serial!r}"]


def _validate_references(document: dict[str, Any]) -> list[str]:
    root_ref = document["metadata"]["component"]["bom-ref"]
    component_refs = {component["bom-ref"] for component in document["components"]}
    tool_refs = {tool["bom-ref"] for tool in document["metadata"]["tools"]["components"]}
    every_ref = list(
        _bom_refs([
            document["metadata"]["component"],
            *document["components"],
            *document["metadata"]["tools"]["components"],
        ])
    )
    if duplicates := {ref for ref in every_ref if every_ref.count(ref) > 1}:
        return [f"bom-ref values are not unique: {sorted(duplicates)}"]
    known = set(every_ref)

    problems = []
    dependencies = {entry["ref"]: set(entry.get("dependsOn", [])) for entry in document["dependencies"]}
    if unknown := (set(dependencies) | set().union(*dependencies.values())) - known:
        problems.append(f"dependencies reference bom-refs that do not exist: {sorted(unknown)}")
    if dependencies.get(root_ref) != component_refs:
        problems.append(
            f"root dependsOn {sorted(dependencies.get(root_ref, []))} != components {sorted(component_refs)}"
        )

    for workflow in document["formulation"][0]["workflows"]:
        referenced = {reference["ref"] for reference in workflow["resourceReferences"]}
        if unknown := referenced - tool_refs:
            problems.append(f"workflow {workflow['uid']} references unknown tools: {sorted(unknown)}")
    return problems


def _validate_spdx(document: dict[str, Any]) -> list[str]:
    try:
        spdx = JsonLikeDictParser().parse(to_spdx(document))
    except SPDXParsingError as error:
        return [f"SPDX rendering does not parse: {message}" for message in error.get_messages()]
    return [f"SPDX rendering invalid: {message.validation_message}" for message in validate_full_spdx_document(spdx)]


def _described_files(components: list[_Component]) -> Iterator[tuple[str, str]]:
    for component in components:
        digest = next((entry["content"] for entry in component.get("hashes", []) if entry["alg"] == "SHA-256"), "")
        if component["type"] == "file":
            yield component["name"], digest
        # an embedded wheel is a library component whose bytes are one archive member
        yield from (
            (prop["value"], digest)
            for prop in component.get("properties", [])
            if prop["name"] == "virtualenv:bundled-wheel"
        )
        yield from _described_files(component.get("components", []))


def _bom_refs(components: list[dict[str, Any]]) -> Iterator[str]:
    for component in components:
        yield component["bom-ref"]
        yield from _bom_refs(component.get("components", []))


if __name__ == "__main__":
    main()
