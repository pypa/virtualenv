"""Check that a built wheel's embedded SBOM is valid CycloneDX 1.6 and satisfies what actions/attest requires."""

from __future__ import annotations

import json
import re
import sys
import zipfile
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final

from cyclonedx.schema import SchemaVersion
from cyclonedx.validation.json import JsonStrictValidator

if TYPE_CHECKING:
    from collections.abc import Iterator

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


def main() -> None:
    directory = Path(sys.argv[1])
    wheels = sorted(directory.glob("*.whl"))
    if len(wheels) != 1:
        msg = f"expected exactly one wheel in {directory}, found {len(wheels)}: {[w.name for w in wheels]}"
        raise SystemExit(msg)
    wheel = wheels[0]
    problems = validate(wheel)
    if problems:
        for problem in problems:
            print(f"SBOM invalid: {problem}")  # ruff:ignore[print]
        raise SystemExit(1)
    print(f"SBOM in {wheel.name} is valid")  # ruff:ignore[print]


def validate(wheel: Path) -> list[str]:
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


def _bom_refs(components: list[dict[str, Any]]) -> Iterator[str]:
    for component in components:
        yield component["bom-ref"]
        yield from _bom_refs(component.get("components", []))


if __name__ == "__main__":
    main()
