"""Check a built wheel's embedded SBOM (CycloneDX 1.6, actions/attest, SPDX 2.3) and the OpenVEX document against it."""

from __future__ import annotations

import hashlib
import json
import re
import sys
import zipfile
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final
from urllib.request import urlopen

from cyclonedx.schema import SchemaVersion
from cyclonedx.validation.json import JsonStrictValidator
from cyclonedx_to_spdx import to_spdx
from jsonschema import Draft202012Validator
from spdx_tools.spdx.parser.error import SPDXParsingError
from spdx_tools.spdx.parser.jsonlikedict.json_like_dict_parser import JsonLikeDictParser
from spdx_tools.spdx.validation.document_validator import validate_full_spdx_document

if TYPE_CHECKING:
    from collections.abc import Iterator
    from typing import NotRequired, TypedDict

    _Hashes = TypedDict("_Hashes", {"sha-256": NotRequired[str]})
    _Subcomponent = TypedDict("_Subcomponent", {"@id": str, "hashes": NotRequired[_Hashes]})

    class _Product(TypedDict):
        subcomponents: NotRequired[list[_Subcomponent]]

    class _Statement(TypedDict):
        products: list[_Product]

    class _OpenVex(TypedDict):
        statements: list[_Statement]


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
_OPENVEX_SCHEMA: Final[str] = (
    "https://raw.githubusercontent.com/openvex/spec/61b5f885d0f481f48683c93345e49ef1a6e9fdff/openvex_json_schema.json"
)
_OPENVEX_SCHEMA_SHA256: Final[str] = "9373597734ed1d3ea5161a8b46d3866c4a8cfe76fd632fdd16aef01fb34b3238"


def main() -> None:
    directory = Path(sys.argv[1])
    wheels = sorted(directory.glob("*.whl"))
    if len(wheels) != 1:
        msg = f"expected exactly one wheel in {directory}, found {len(wheels)}: {[w.name for w in wheels]}"
        raise SystemExit(msg)
    wheel = wheels[0]
    vex = Path(sys.argv[2])
    problems = validate(wheel, vex)
    if problems:
        for problem in problems:
            print(f"SBOM invalid: {problem}")  # ruff:ignore[print]
        raise SystemExit(1)
    print(f"SBOM in {wheel.name} and {vex.name} are valid")  # ruff:ignore[print]


def validate(wheel: Path, vex: Path) -> list[str]:
    with zipfile.ZipFile(wheel) as archive:
        sbom_name = next((n for n in archive.namelist() if n.endswith("/sboms/virtualenv.cdx.json")), None)
        if sbom_name is None:
            return ["no .dist-info/sboms/virtualenv.cdx.json found in the wheel"]
        raw = archive.read(sbom_name).decode("utf-8")

    if schema_error := JsonStrictValidator(SchemaVersion.V1_6).validate_str(raw):
        return [f"does not conform to the CycloneDX 1.6 schema: {schema_error}"]
    document = json.loads(raw)

    problems = []
    if not _SERIAL_PATTERN.match(document.get("serialNumber", "")):
        # optional in the CycloneDX spec itself, but actions/attest's format sniffer requires it to recognize
        # the document as CycloneDX at all, and silently rejects anything missing it as an unknown format
        problems.append(f"serialNumber must be a urn:uuid: RFC 4122 UUID, got {document.get('serialNumber')!r}")
    problems += _validate_references(document)
    problems += _validate_spdx(document)
    problems += _validate_vex(
        vex,
        {
            (component["purl"], digest["content"])
            for component in document["components"]
            for digest in component.get("hashes", [])
            if digest["alg"] == "SHA-256"
        },
    )
    return problems


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


def _validate_vex(vex: Path, bundled: set[tuple[str, str]]) -> list[str]:
    with urlopen(_OPENVEX_SCHEMA) as response:
        schema: Final[bytes] = response.read()
    if (digest := hashlib.sha256(schema).hexdigest()) != _OPENVEX_SCHEMA_SHA256:
        return [f"OpenVEX schema at {_OPENVEX_SCHEMA} has SHA-256 {digest}, expected {_OPENVEX_SCHEMA_SHA256}"]
    document: Final[_OpenVex] = json.loads(vex.read_text(encoding="utf-8"))
    if errors := [error.message for error in Draft202012Validator(json.loads(schema)).iter_errors(document)]:
        return [f"{vex.name} does not conform to the OpenVEX schema: {error}" for error in errors]
    subcomponents: Final[set[tuple[str, str]]] = {
        (subcomponent["@id"], subcomponent.get("hashes", {}).get("sha-256", ""))
        for statement in document["statements"]
        for product in statement["products"]
        for subcomponent in product.get("subcomponents", [])
    }
    # a statement about a wheel virtualenv no longer bundles, or one whose hash changed, would mislead scanners
    if unknown := subcomponents - bundled:
        return [f"{vex.name} names subcomponents the wheel does not bundle: {sorted(unknown)}"]
    return []


def _bom_refs(components: list[dict[str, Any]]) -> Iterator[str]:
    for component in components:
        yield component["bom-ref"]
        yield from _bom_refs(component.get("components", []))


if __name__ == "__main__":
    main()
