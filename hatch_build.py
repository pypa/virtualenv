from __future__ import annotations

import ast
import base64
import csv
import hashlib
import json
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import uuid
import zipfile
from datetime import datetime, timezone
from email.parser import Parser
from email.utils import getaddresses
from importlib.metadata import distributions
from io import StringIO
from itertools import starmap
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final

from hatchling.builders.hooks.plugin.interface import BuildHookInterface
from hatchling.builders.utils import get_reproducible_timestamp
from packaging.requirements import Requirement

if TYPE_CHECKING:
    from importlib.metadata import Distribution, PackageMetadata

    from hatchling.metadata.core import CoreMetadata

_ROOT: Final[Path] = Path(__file__).resolve().parent
_EMBED: Final[Path] = _ROOT / "src" / "virtualenv" / "seed" / "wheels" / "embed"
_REPOSITORY: Final[str] = "https://github.com/pypa/virtualenv"
_SBOM_NAMESPACE: Final[uuid.UUID] = uuid.uuid5(uuid.NAMESPACE_URL, f"{_REPOSITORY}/sboms")
_PYPA: Final[dict[str, Any]] = {"name": "Python Packaging Authority", "url": ["https://www.pypa.io"]}
# the label normalization and mapping cyclonedx-py applies to Project-URL entries, plus "source", so the same
# metadata yields the same reference types whichever generator produced the document
_URL_LABEL_TO_REFERENCE_TYPE: Final[dict[str, str]] = {
    "bugtracker": "issue-tracker",
    "issuetracker": "issue-tracker",
    "issues": "issue-tracker",
    "bugreports": "issue-tracker",
    "tracker": "issue-tracker",
    "home": "website",
    "homepage": "website",
    "download": "distribution",
    "documentation": "documentation",
    "docs": "documentation",
    "changelog": "release-notes",
    "changes": "release-notes",
    "source": "vcs",
    "repository": "vcs",
    "github": "vcs",
    "chat": "chat",
}
# core metadata headers copied verbatim onto a component as properties
_METADATA_PROPERTIES: Final[tuple[str, ...]] = (
    "Requires-Python",
    "Requires-Dist",
    "Provides-Extra",
    "Classifier",
    "Keywords",
)
_RECORD_HASH_ALGORITHMS: Final[dict[str, str]] = {
    "md5": "MD5",
    "sha1": "SHA-1",
    "sha256": "SHA-256",
    "sha384": "SHA-384",
    "sha512": "SHA-512",
}


class SbomBuildHook(BuildHookInterface):
    """Write a PEP 770 CycloneDX SBOM into the wheel's ``.dist-info/sboms/`` directory.

    General-purpose SBOM scanners (syft, cyclonedx-py, GitHub's dependency graph) read declared dependency metadata or
    an installed environment, and virtualenv's bundled pip and setuptools wheels are neither: they are data files
    embedded under ``src/virtualenv/seed/wheels/embed/``, invisible to every one of those tools. Each bundled wheel is
    described from its own ``METADATA`` and ``RECORD`` and hashed from its bytes, so a wheel bump needs no separate SBOM
    update.

    The document also records the build environment (interpreter, OS, every distribution in the isolated build env with
    its files and the dependency graph between them), which PEP 770 calls out as what a third party needs to verify
    build reproducibility, plus the source revision when known. Release attestations identify the CI run without
    introducing run-specific values into the wheel.

    """

    PLUGIN_NAME = "sbom"

    def initialize(self, version: str, build_data: dict[str, Any]) -> None:  # ruff:ignore[unused-method-argument]
        # `version` here is hatchling's build variant name (e.g. "standard"), not the package version
        if self.target_name != "wheel" or "sbom_files" not in build_data:
            # sbom_files only exists on hatchling>=1.28, which build-system.requires excludes for the
            # Python versions old enough to still need hatchling<1.28 for building at all
            return
        document = _cyclonedx_document(self.metadata.core, self.metadata.version)
        # written outside self.directory, which hatchling also uses as the final wheel output location, so a
        # stray copy here would sit next to the built artifacts and trip `twine check dist/*`
        out = Path(tempfile.mkdtemp(prefix="virtualenv-sbom-")) / "virtualenv.cdx.json"
        out.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
        build_data["sbom_files"].append(str(out))


def _cyclonedx_document(core: CoreMetadata, version: str) -> dict[str, Any]:
    root = _root_component(core, version)
    bundled = [_bundled_component(wheel) for wheel in sorted(_EMBED.glob("*.whl"))]
    declared = [_declared_dependency(requirement) for requirement in core.dependencies]
    tools, tool_dependencies = _build_tools(version)
    body = {
        "metadata": {
            "timestamp": _timestamp(),
            "lifecycles": [{"phase": "build"}],
            "tools": {"components": tools},
            "manufacturer": _PYPA,
            "authors": _contacts(core.maintainers_data["name"], core.maintainers_data["email"]),
            "supplier": _PYPA,
            "component": root,
            "licenses": [{"expression": core.license_expression, "acknowledgement": "declared"}],
            "properties": [
                {
                    "name": "virtualenv:sbom:scope",
                    "value": "Components are the wheels bundled as data files under src/virtualenv/seed/wheels/embed"
                    " and the direct runtime dependencies declared in the wheel's core metadata. The latter carry"
                    " no version because they are resolved at install time, not at build time.",
                },
            ],
        },
        "components": [*bundled, *declared],
        "dependencies": [
            {"ref": root["bom-ref"], "dependsOn": [component["bom-ref"] for component in [*bundled, *declared]]},
            *tool_dependencies,
        ],
        # transitive runtime dependencies are unknown until install time
        "compositions": [{"aggregate": "incomplete", "dependencies": [root["bom-ref"]]}],
        "formulation": [{"bom-ref": "formula:wheel-build", "workflows": [_workflow(root, tools)]}],
    }
    return {
        "$schema": "http://cyclonedx.org/schema/bom-1.6.schema.json",
        "bomFormat": "CycloneDX",
        "specVersion": "1.6",
        # derived from the content so identical documents share a serial and any difference gets a new one
        "serialNumber": f"urn:uuid:{uuid.uuid5(_SBOM_NAMESPACE, json.dumps(body, sort_keys=True))}",
        "version": 1,
        **body,
    }


def _root_component(core: CoreMetadata, version: str) -> dict[str, Any]:
    purl = _purl(core.name, version)
    wheel_name = f"{core.name}-{version}-py3-none-any.whl"
    license_lines = (_ROOT / "LICENSE").read_text(encoding="utf-8").splitlines()
    references = list(starmap(_external_reference, core.urls.items()))
    references += [
        {"type": "distribution", "url": f"https://pypi.org/project/{core.name}/{version}/"},
        {"type": "attestation", "url": f"https://pypi.org/integrity/{core.name}/{version}/{wheel_name}/provenance"},
        {"type": "release-notes", "url": "https://virtualenv.pypa.io/en/latest/changelog.html"},
        {"type": "security-contact", "url": f"{_REPOSITORY}/security/policy"},
        {"type": "advisories", "url": f"{_REPOSITORY}/security/advisories"},
        {"type": "license", "url": f"{_REPOSITORY}/blob/main/LICENSE"},
    ]
    properties = [
        {"name": "virtualenv:requires-python", "value": core.requires_python},
        *({"name": "python:classifier", "value": classifier} for classifier in core.classifiers),
        *({"name": "python:keyword", "value": keyword} for keyword in core.keywords),
    ]
    if commit := _commit():
        references.append({"type": "vcs", "url": f"{_REPOSITORY}/tree/{commit}", "comment": "exact source revision"})
        properties.append({"name": "virtualenv:vcs-commit", "value": commit})
    return {
        "type": "application",
        "bom-ref": purl,
        "supplier": _PYPA,
        "authors": _contacts(core.maintainers_data["name"], core.maintainers_data["email"]),
        "name": core.name,
        "version": version,
        "description": core.description,
        "licenses": [{"expression": core.license_expression, "acknowledgement": "declared"}],
        "copyright": next(line for line in license_lines if line.startswith("Copyright")),
        "purl": purl,
        "externalReferences": references,
        "properties": properties,
    }


def _purl(name: str, version: str | None = None) -> str:
    normalized = re.sub(r"[-_.]+", "-", name).lower()
    return f"pkg:pypi/{normalized}@{version}" if version else f"pkg:pypi/{normalized}"


def _external_reference(label: str, url: str) -> dict[str, str]:
    reference_type = _URL_LABEL_TO_REFERENCE_TYPE.get(re.sub(r"[^a-z]", "", label.lower()), "other")
    return {"type": reference_type, "url": url, "comment": f"Project-URL: {label}"}


def _commit() -> str | None:
    if not (_ROOT / ".git").exists() or (git := shutil.which("git")) is None:  # building from an sdist
        return None
    return subprocess.run(
        [git, "rev-parse", "HEAD"], check=True, capture_output=True, text=True, cwd=_ROOT
    ).stdout.strip()


def _contacts(names: list[str], addresses: list[str]) -> list[dict[str, str]]:
    contacts = [{"name": name} for name in names]
    for name, email in getaddresses(addresses):
        contacts.append({key: value for key, value in (("name", name), ("email", email)) if value})
    return contacts


def _bundled_component(wheel: Path) -> dict[str, Any]:
    with zipfile.ZipFile(wheel) as archive:
        metadata_name = next(name for name in archive.namelist() if name.endswith(".dist-info/METADATA"))
        metadata = Parser().parsestr(archive.read(metadata_name).decode("utf-8"))
        record = archive.read(metadata_name.replace("METADATA", "RECORD")).decode("utf-8")
    component = _component_from_metadata(metadata, "library")
    if any(reference["url"].startswith("https://github.com/pypa/") for reference in component["externalReferences"]):
        component["supplier"] = _PYPA
    sha256 = hashlib.sha256(wheel.read_bytes()).hexdigest()
    component["hashes"] = [{"alg": "SHA-256", "content": sha256}]
    component["externalReferences"].append(
        {"type": "distribution", "url": f"https://pypi.org/project/{metadata['Name']}/{metadata['Version']}/"},
    )
    component["properties"] = [
        {"name": "virtualenv:bundled-wheel", "value": wheel.relative_to(_ROOT).as_posix()},
        *(
            {"name": "virtualenv:seeded-for-python", "value": python_version}
            for python_version, wheels in _bundle_support().items()
            if wheel.name in wheels.values()
        ),
        *component["properties"],
    ]
    component["evidence"] = {
        "identity": [
            {
                "field": "purl",
                "confidence": 1,
                "methods": [{"technique": "manifest-analysis", "confidence": 1, "value": metadata_name}],
            },
            {
                "field": "hash",
                "confidence": 1,
                "methods": [{"technique": "hash-comparison", "confidence": 1, "value": sha256}],
            },
        ],
    }
    component["components"] = [
        _file_component(component["bom-ref"], path, digest, size)
        for path, digest, size in (row for row in csv.reader(StringIO(record, newline="")) if row)
        if digest
    ]
    return component


def _component_from_metadata(metadata: PackageMetadata, component_type: str) -> dict[str, Any]:
    name, version = metadata["Name"], metadata["Version"]
    purl = _purl(name, version)
    component: dict[str, Any] = {
        "type": component_type,
        "bom-ref": purl,
        "name": name,
        "version": version,
        "purl": purl,
    }
    if summary := metadata.get("Summary"):
        component["description"] = summary
    if authors := _contacts(
        metadata.get_all("Author", []) + metadata.get_all("Maintainer", []),
        metadata.get_all("Author-email", []) + metadata.get_all("Maintainer-email", []),
    ):
        component["authors"] = authors
    if licenses := _licenses(metadata):
        component["licenses"] = licenses
    component["externalReferences"] = [
        _external_reference(label.strip(), url.strip())
        for label, url in (entry.split(",", 1) for entry in metadata.get_all("Project-URL", []))
    ]
    if home_page := metadata.get("Home-page"):
        component["externalReferences"].insert(0, {"type": "website", "url": home_page})
    component["properties"] = [
        {"name": f"python:{header.lower()}", "value": value}
        for header in _METADATA_PROPERTIES
        for value in metadata.get_all(header, [])
    ]
    return component


def _licenses(metadata: PackageMetadata) -> list[dict[str, Any]]:
    if expression := metadata.get("License-Expression"):
        return [{"expression": expression, "acknowledgement": "declared"}]
    names = [
        entry.rsplit(" :: ", 1)[-1] for entry in metadata.get_all("Classifier", []) if entry.startswith("License :: ")
    ]
    if (declared := metadata.get("License")) and "\n" not in declared:
        names.append(declared)
    return [{"license": {"name": name, "acknowledgement": "declared"}} for name in names]


def _bundle_support() -> dict[str, dict[str, str]]:
    tree = ast.parse((_EMBED / "__init__.py").read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "BUNDLE_SUPPORT" for target in node.targets
        ):
            return ast.literal_eval(node.value)
    msg = f"BUNDLE_SUPPORT not found in {_EMBED / '__init__.py'}"
    raise RuntimeError(msg)


def _file_component(parent_ref: str, path: str, digest: str, size: str) -> dict[str, Any]:
    # RECORD stores "<algorithm>=<urlsafe base64 without padding>", CycloneDX wants lowercase hex
    algorithm, _, encoded = digest.partition("=")
    raw = base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4))
    return {
        "type": "file",
        "bom-ref": f"{parent_ref}#{path}",
        "name": path,
        "hashes": [{"alg": _RECORD_HASH_ALGORITHMS[algorithm], "content": raw.hex()}],
        "properties": [{"name": "size", "value": size}],
    }


def _declared_dependency(requirement: str) -> dict[str, Any]:
    parsed = Requirement(requirement)
    component = {
        "type": "library",
        # the same distribution can be declared more than once with different markers, so the purl alone is not unique
        "bom-ref": f"requires-dist:{requirement}",
        "name": parsed.name,
        "purl": _purl(parsed.name),
        "externalReferences": [{"type": "distribution", "url": f"https://pypi.org/project/{parsed.name}/"}],
        "properties": [{"name": "virtualenv:requires-dist", "value": requirement}],
    }
    if parsed.marker is not None:
        component["properties"].append({"name": "virtualenv:environment-marker", "value": str(parsed.marker)})
    return component


def _build_tools(package_version: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    hook = Path(__file__)
    interpreter = f"pkg:generic/{sys.implementation.name}@{platform.python_version()}"
    tools = [
        {
            "type": "application",
            "bom-ref": "tool:hatch_build.py",
            "name": hook.name,
            "version": package_version,
            "hashes": [{"alg": "SHA-256", "content": hashlib.sha256(hook.read_bytes()).hexdigest()}],
            "externalReferences": [{"type": "vcs", "url": f"{_REPOSITORY}/blob/main/hatch_build.py"}],
        },
        {
            "type": "platform",
            "bom-ref": f"tool:{interpreter}",
            "name": sys.implementation.name,
            "version": platform.python_version(),
            "description": sys.version,
            "purl": interpreter,
            "properties": [
                {"name": "python:implementation", "value": platform.python_implementation()},
                {"name": "python:compiler", "value": platform.python_compiler()},
                # GraalPy may omit the build date instead of returning an empty string.
                {"name": "python:build", "value": " ".join(part for part in platform.python_build() if part)},
            ],
        },
        _operating_system(),
    ]
    # bom-refs are prefixed because the same distribution can be both a build tool and a bundled component
    installed = {_purl(distribution.metadata["Name"]): distribution for distribution in distributions()}
    tool_dependencies = []
    for distribution in (installed[key] for key in sorted(installed)):
        component = _component_from_metadata(distribution.metadata, "library")
        component["bom-ref"] = f"tool:{component['purl']}"
        component["components"] = [
            _file_component(
                component["bom-ref"], file.as_posix(), f"{file.hash.mode}={file.hash.value}", str(file.size)
            )
            for file in distribution.files or []
            # console-script launchers live outside site-packages and embed the build env's interpreter path in
            # their shebang, so their hash differs on every build and says nothing about the distribution
            if file.hash is not None and not file.as_posix().startswith("../")
        ]
        tools.append(component)
        tool_dependencies.append({"ref": component["bom-ref"], "dependsOn": _depends_on(distribution, installed)})
    return tools, tool_dependencies


def _operating_system() -> dict[str, Any]:
    component: dict[str, Any] = {
        "type": "operating-system",
        "bom-ref": f"tool:os:{platform.system()}@{platform.release()}",
        "name": platform.system(),
        "version": platform.release(),
        "description": platform.platform(),
        "properties": [
            {"name": "machine", "value": platform.machine()},
            {"name": "kernel-version", "value": platform.version()},
        ],
    }
    try:
        os_release = platform.freedesktop_os_release()
    except OSError:  # not a freedesktop system, e.g. macOS or Windows
        return component
    component["properties"] += [
        {"name": f"os-release:{key}", "value": value} for key, value in sorted(os_release.items())
    ]
    return component


def _depends_on(distribution: Distribution, installed: dict[str, Distribution]) -> list[str]:
    refs = set()
    for requirement in map(Requirement, distribution.requires or []):
        if (requirement.marker is None or requirement.marker.evaluate()) and (
            dependency := installed.get(_purl(requirement.name))
        ):
            refs.add(f"tool:{_purl(dependency.metadata['Name'], dependency.version)}")
    return sorted(refs)


def _workflow(root: dict[str, Any], tools: list[dict[str, Any]]) -> dict[str, Any]:
    workflow: dict[str, Any] = {
        "bom-ref": "workflow:wheel-build",
        "uid": "wheel-build",
        "name": "build the wheel and this SBOM",
        "taskTypes": ["build"],
        "resourceReferences": [{"ref": tool["bom-ref"]} for tool in tools],
        "outputs": [{"type": "artifact", "resource": {"ref": root["bom-ref"]}}],
    }
    workflow["inputs"] = [
        {"environmentVars": [{"name": "SOURCE_DATE_EPOCH", "value": str(get_reproducible_timestamp())}]},
    ]
    return workflow


def _timestamp() -> str:
    return datetime.fromtimestamp(get_reproducible_timestamp(), tz=timezone.utc).isoformat()
