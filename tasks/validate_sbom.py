"""Check that a built wheel's embedded SBOM satisfies what a consumer like actions/attest requires."""

from __future__ import annotations

import json
import re
import sys
import zipfile
from pathlib import Path
from typing import Any

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
    print(f"SBOM in {wheel.name} is structurally valid")  # ruff:ignore[print]


def validate(wheel: Path) -> list[str]:
    with zipfile.ZipFile(wheel) as archive:
        names = archive.namelist()
        sbom_name = next((name for name in names if name.endswith("/sboms/virtualenv.cdx.json")), None)
        if sbom_name is None:
            return ["no .dist-info/sboms/virtualenv.cdx.json found in the wheel"]
        document = json.loads(archive.read(sbom_name))

    problems = []
    if document.get("bomFormat") != "CycloneDX":
        problems.append(f"bomFormat must be 'CycloneDX', got {document.get('bomFormat')!r}")
    if document.get("specVersion") != "1.6":
        problems.append(f"specVersion must be '1.6', got {document.get('specVersion')!r}")
    if document.get("version") != 1:
        problems.append(f"version must be 1, got {document.get('version')!r}")

    serial = document.get("serialNumber")
    if not serial or not _SERIAL_PATTERN.match(serial):
        # optional in the CycloneDX spec itself, but actions/attest's format sniffer requires it to recognize
        # the document as CycloneDX at all, and silently rejects anything missing it as an unknown format
        problems.append(f"serialNumber must match {_SERIAL_PATTERN.pattern}, got {serial!r}")

    metadata_problems, root_ref = _validate_metadata(document.get("metadata", {}))
    problems += metadata_problems
    problems += _validate_dependency_graph(document, root_ref)
    return problems


def _validate_metadata(metadata: dict[str, Any]) -> tuple[list[str], str | None]:
    problems = []
    if not metadata.get("timestamp"):
        problems.append("metadata.timestamp is missing")
    if not metadata.get("tools", {}).get("components"):
        problems.append("metadata.tools.components is missing or empty")
    root_ref = metadata.get("component", {}).get("bom-ref")
    if not root_ref:
        problems.append("metadata.component.bom-ref is missing")
    return problems, root_ref


def _validate_dependency_graph(document: dict[str, Any], root_ref: str | None) -> list[str]:
    problems = []
    component_refs = {component.get("bom-ref") for component in document.get("components", [])}
    dependency_entries = {
        entry.get("ref"): set(entry.get("dependsOn", [])) for entry in document.get("dependencies", [])
    }
    unknown_refs = set(dependency_entries) - component_refs - {root_ref}
    if unknown_refs:
        problems.append(f"dependencies entries with no matching component: {sorted(unknown_refs)}")

    root_depends_on = dependency_entries.get(root_ref)
    if root_depends_on is None:
        problems.append(f"no dependencies entry for the root component {root_ref!r}")
    elif root_depends_on != component_refs:
        problems.append(f"root dependsOn {sorted(root_depends_on)} does not match components {sorted(component_refs)}")
    return problems


if __name__ == "__main__":
    main()
