"""Check that a built wheel's embedded SBOM is valid CycloneDX 1.6 and satisfies what actions/attest requires."""

from __future__ import annotations

import json
import re
import sys
import zipfile
from pathlib import Path
from typing import Any

from cyclonedx.schema import SchemaVersion
from cyclonedx.validation.json import JsonStrictValidator

_SERIAL_PATTERN = re.compile(r"^urn:uuid:[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


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
        problems.append(f"serialNumber must match {_SERIAL_PATTERN.pattern}, got {document.get('serialNumber')!r}")
    problems += _validate_references(document)
    return problems


def _validate_references(document: dict[str, Any]) -> list[str]:
    root_ref = document["metadata"]["component"]["bom-ref"]
    component_refs = {component["bom-ref"] for component in document["components"]}
    tool_refs = {tool["bom-ref"] for tool in document["metadata"]["tools"]["components"]}
    known = {root_ref, *component_refs, *tool_refs}
    if len(known) != 1 + len(document["components"]) + len(tool_refs):
        return ["bom-ref values are not unique across the root, components and tools"]

    problems = []
    dependencies = {entry["ref"]: set(entry.get("dependsOn", [])) for entry in document["dependencies"]}
    if unknown := (set(dependencies) | set().union(*dependencies.values())) - known:
        problems.append(f"dependencies reference bom-refs that do not exist: {sorted(unknown)}")
    if dependencies.get(root_ref) != component_refs:
        problems.append(
            f"root dependsOn {sorted(dependencies.get(root_ref, []))} != components {sorted(component_refs)}"
        )
    if missing := component_refs - set(dependencies):
        problems.append(f"components without a dependencies entry: {sorted(missing)}")

    for workflow in document["formulation"][0]["workflows"]:
        referenced = {reference["ref"] for reference in workflow["resourceReferences"]}
        if unknown := referenced - tool_refs:
            problems.append(f"workflow {workflow['uid']} references unknown tools: {sorted(unknown)}")
    return problems


if __name__ == "__main__":
    main()
