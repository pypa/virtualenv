"""Describe what a built virtualenv zipapp contains as a CycloneDX SBOM, and embed that SBOM in the zipapp."""

from __future__ import annotations

import hashlib
import json
import sys
import uuid
import zipfile
from datetime import datetime, timezone
from importlib.metadata import PathDistribution
from io import BytesIO
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, Final, cast
from urllib.parse import quote

from hatchling.builders.utils import get_reproducible_timestamp

from hatch_build import PYPA, SBOM_NAMESPACE, build_tools, component_from_metadata, timestamp

if TYPE_CHECKING:
    from importlib.metadata import PackageMetadata
    from typing import NotRequired, TypedDict

    class _Hash(TypedDict):
        alg: str
        content: str

    class _Property(TypedDict):
        name: str
        value: str

    class _Reference(TypedDict):
        type: str
        url: str
        comment: NotRequired[str]

    _Component = TypedDict(
        "_Component",
        {
            "type": str,
            "bom-ref": str,
            "name": str,
            "version": NotRequired[str],
            "purl": NotRequired[str],
            "supplier": NotRequired[dict[str, str | list[str]]],
            "description": NotRequired[str],
            "hashes": NotRequired[list[_Hash]],
            "externalReferences": NotRequired[list[_Reference]],
            "properties": NotRequired[list[_Property]],
            "components": NotRequired[list["_Component"]],
        },
    )

_SBOM_NAME: Final[str] = "virtualenv.pyz.cdx.json"
_HERE: Final[Path] = Path(__file__).parent
_RELEASES: Final[str] = "https://github.com/pypa/virtualenv/releases/download"
_BUNDLED: Final[str] = "__virtualenv__/"
_EMBEDDED_WHEELS: Final[str] = "virtualenv/seed/wheels/embed/"
# written by tasks/make_zipapp.py to find modules and metadata of the bundled distributions at run time
_LOADER: Final[frozenset[str]] = frozenset({"__main__.py", "distributions.json", "modules.json"})


def main() -> None:
    pyz, target = map(Path, sys.argv[1:3])
    with zipfile.ZipFile(pyz) as archive:
        content: Final[str] = _describe(archive)
    target.write_text(content, encoding="utf-8")
    entry: Final[zipfile.ZipInfo] = zipfile.ZipInfo(
        _SBOM_NAME, datetime.fromtimestamp(get_reproducible_timestamp(), tz=timezone.utc).timetuple()[:6]
    )
    with zipfile.ZipFile(pyz, "a") as archive:
        archive.writestr(entry, content)


def _describe(archive: zipfile.ZipFile) -> str:
    members: Final[list[str]] = sorted(name for name in archive.namelist() if not name.endswith("/"))
    metadata: Final[PackageMetadata] = _metadata(
        archive, next(name for name in members if name.count("/") == 1 and name.endswith(".dist-info/METADATA"))
    )
    version: Final[str] = metadata["Version"]
    purl: Final[str] = f"pkg:generic/virtualenv.pyz@{quote(version, safe='')}"
    root: Final[_Component] = {
        "type": "application",
        "bom-ref": purl,
        "supplier": PYPA,
        "name": "virtualenv.pyz",
        "version": version,
        "description": "virtualenv and its runtime dependencies for every supported Python, as one zipapp",
        "purl": purl,
        "externalReferences": [
            {"type": "distribution", "url": f"{_RELEASES}/{version}/virtualenv.pyz"},
            {"type": "distribution", "url": "https://bootstrap.pypa.io/virtualenv.pyz", "comment": "latest release"},
        ],
        "components": [_file(archive, purl, name) for name in members if name in _LOADER],
    }
    virtualenv: Final[_Component] = _from_metadata(metadata)
    # the wheel SBOM in virtualenv's dist-info already lists what each embedded wheel vendors
    virtualenv["components"] = [
        _embedded_wheel(archive, name)
        if name.startswith(_EMBEDDED_WHEELS) and name.endswith(".whl")
        else _file(archive, virtualenv["bom-ref"], name)
        for name in members
        if not name.startswith(_BUNDLED) and name not in _LOADER and name != _SBOM_NAME
    ]
    loaded_by: Final[dict[str, list[str]]] = {}
    for python, platforms in json.loads(archive.read("distributions.json")).items():
        for paths in platforms.values():
            for path in paths.values():
                loaded_by.setdefault(str(PurePosixPath(path).parent), []).append(python)
    bundled: Final[list[_Component]] = [
        _bundled(archive, directory, [name for name in members if name.startswith(f"{directory}/")], pythons)
        for directory, pythons in sorted(loaded_by.items())
    ]
    environment, tool_dependencies = build_tools(version)
    tools: Final = [*environment, *(_script(path, version) for path in (_HERE / "make_zipapp.py", Path(__file__)))]
    body: Final = {
        "metadata": {
            "timestamp": timestamp(),
            "lifecycles": [{"phase": "build"}],
            "tools": {"components": tools},
            "manufacturer": PYPA,
            "supplier": PYPA,
            "component": root,
        },
        "components": [virtualenv, *bundled],
        "dependencies": [
            {"ref": purl, "dependsOn": [virtualenv["bom-ref"], *(component["bom-ref"] for component in bundled)]},
            *tool_dependencies,
        ],
        "formulation": [
            {
                "bom-ref": "formula:zipapp-build",
                "workflows": [
                    {
                        "bom-ref": "workflow:zipapp-build",
                        "uid": "zipapp-build",
                        "name": "build the zipapp and this SBOM",
                        "taskTypes": ["build"],
                        "resourceReferences": [{"ref": tool["bom-ref"]} for tool in tools],
                        "inputs": [
                            {
                                "environmentVars": [
                                    {"name": "SOURCE_DATE_EPOCH", "value": str(get_reproducible_timestamp())}
                                ]
                            }
                        ],
                        "outputs": [{"type": "artifact", "resource": {"ref": purl}}],
                    }
                ],
            }
        ],
    }
    document: Final = {
        "$schema": "http://cyclonedx.org/schema/bom-1.6.schema.json",
        "bomFormat": "CycloneDX",
        "specVersion": "1.6",
        # derived from the content so identical documents share a serial and any difference gets a new one
        "serialNumber": f"urn:uuid:{uuid.uuid5(SBOM_NAMESPACE, json.dumps(body, sort_keys=True))}",
        "version": 1,
        **body,
    }
    return json.dumps(document, indent=2) + "\n"


def _metadata(archive: zipfile.ZipFile, name: str) -> PackageMetadata:
    return PathDistribution(zipfile.Path(archive, f"{PurePosixPath(name).parent}/")).metadata


def _from_metadata(metadata: PackageMetadata) -> _Component:
    # hatch_build.py builds its CycloneDX dicts untyped; this is where they enter typed code
    return cast("_Component", component_from_metadata(metadata, "library"))


def _file(archive: zipfile.ZipFile, parent: str, name: str) -> _Component:
    content: Final[bytes] = archive.read(name)
    return {
        "type": "file",
        "bom-ref": f"{parent}#{name}",
        "name": name,
        "hashes": [{"alg": "SHA-256", "content": hashlib.sha256(content).hexdigest()}],
        "properties": [{"name": "size", "value": str(len(content))}],
    }


def _embedded_wheel(archive: zipfile.ZipFile, name: str) -> _Component:
    content: Final[bytes] = archive.read(name)
    with zipfile.ZipFile(BytesIO(content)) as wheel:
        metadata: Final[PackageMetadata] = _metadata(
            wheel, next(entry for entry in wheel.namelist() if entry.endswith(".dist-info/METADATA"))
        )
    component: Final[_Component] = _from_metadata(metadata)
    component["hashes"] = [{"alg": "SHA-256", "content": hashlib.sha256(content).hexdigest()}]
    component["properties"] = [{"name": "virtualenv:bundled-wheel", "value": name}, *component["properties"]]
    return component


def _bundled(archive: zipfile.ZipFile, directory: str, names: list[str], pythons: list[str]) -> _Component:
    component: Final[_Component] = _from_metadata(
        _metadata(archive, next(name for name in names if name.endswith(".dist-info/METADATA")))
    )
    loaded_for: Final[list[_Property]] = [
        {"name": "virtualenv:loaded-for-python", "value": python} for python in pythons
    ]
    component["properties"] = [
        {"name": "virtualenv:zipapp-directory", "value": directory},
        *loaded_for,
        *component["properties"],
    ]
    component["components"] = [_file(archive, component["bom-ref"], name) for name in names]
    return component


def _script(path: Path, version: str) -> _Component:
    return {
        "type": "application",
        "bom-ref": f"tool:{path.name}",
        "name": path.name,
        "version": version,
        "hashes": [{"alg": "SHA-256", "content": hashlib.sha256(path.read_bytes()).hexdigest()}],
        "externalReferences": [
            {"type": "vcs", "url": f"https://github.com/pypa/virtualenv/blob/main/tasks/{path.name}"}
        ],
    }


if __name__ == "__main__":
    main()
