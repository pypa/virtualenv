from __future__ import annotations

import base64
import csv
import hashlib
import json
import runpy
import shutil
import sys
import zipfile
from io import BytesIO, StringIO
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final

import pytest
from hatchling.builders.wheel import WheelBuilder

if TYPE_CHECKING:
    from collections.abc import Callable

    from pytest_mock import MockerFixture

_DISTRIBUTIONS: Final[str] = json.dumps({
    "3.14": {"==any": {"distlib": "__virtualenv__/distlib-0.4-py3-none-any/distlib-0.4.dist-info"}},
    "3.9": {"==any": {"distlib": "__virtualenv__/distlib-0.4-py3-none-any/distlib-0.4.dist-info"}},
})


@pytest.mark.parametrize(
    "filename",
    [
        pytest.param("pip/example.py", id="plain"),
        pytest.param("pip/a,b.py", id="comma"),
        pytest.param('pip/a"b.py', id="quote"),
        pytest.param("pip/a\nb.py", id="newline"),
    ],
)
def test_sbom_record_paths(build_sbom: Callable[[str, dict[str, str]], str], filename: str) -> None:
    assert json.loads(build_sbom(filename, {}))["components"][0]["components"] == [
        {
            "type": "file",
            "bom-ref": f"pkg:pypi/pip@1.0#{filename}",
            "name": filename,
            "hashes": [
                {"alg": "SHA-256", "content": "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"}
            ],
            "properties": [{"name": "size", "value": "3"}],
        },
    ]


def test_sbom_unresolved_dependencies(build_sbom: Callable[[str, dict[str, str]], str]) -> None:
    document: Final[dict[str, Any]] = json.loads(build_sbom("pip/example.py", {}))
    assert [entry for entry in document["dependencies"] if not entry["ref"].startswith("tool:")] == [
        {"ref": "pkg:pypi/virtualenv@1.0", "dependsOn": ["pkg:pypi/pip@1.0", "requires-dist:python-discovery>=1.6"]},
    ]


@pytest.mark.parametrize(
    ("source", "content"),
    [
        pytest.param(
            "pip/_vendor/vendor.txt", "# bundled\n\n  urllib3==1.26.4 # patched upstream\n", id="pip-manifest"
        ),
        pytest.param(
            "pip/_vendor/urllib3-1.26.4.dist-info/METADATA", "Name: urllib3\nVersion: 1.26.4\n", id="nested-metadata"
        ),
    ],
)
def test_sbom_vendored_identity(build_sbom: Callable[[str, dict[str, str]], str], source: str, content: str) -> None:
    document: Final[dict[str, Any]] = json.loads(build_sbom("pip/example.py", {source: content}))
    assert [child for child in document["components"][0]["components"] if child["type"] == "library"] == [
        {
            "type": "library",
            "bom-ref": "pkg:pypi/pip@1.0#vendored/pkg:pypi/urllib3@1.26.4",
            "name": "urllib3",
            "version": "1.26.4",
            "purl": "pkg:pypi/urllib3@1.26.4",
            "externalReferences": [],
            "properties": [{"name": "virtualenv:vendored-manifest", "value": source}],
            "evidence": {
                "identity": [
                    {
                        "field": "purl",
                        "confidence": 1,
                        "methods": [{"technique": "manifest-analysis", "confidence": 1, "value": source}],
                    }
                ]
            },
        }
    ]


def test_sbom_vendored_relationship(build_sbom: Callable[[str, dict[str, str]], str]) -> None:
    document: Final[dict[str, Any]] = json.loads(
        build_sbom("pip/example.py", {"pip/_vendor/vendor.txt": "urllib3==1.26.4\n"})
    )
    assert [entry for entry in document["dependencies"] if not entry["ref"].startswith("tool:")] == [
        {"ref": "pkg:pypi/virtualenv@1.0", "dependsOn": ["pkg:pypi/pip@1.0", "requires-dist:python-discovery>=1.6"]},
        {"ref": "pkg:pypi/pip@1.0", "dependsOn": ["pkg:pypi/pip@1.0#vendored/pkg:pypi/urllib3@1.26.4"]},
    ]


def test_sbom_vendored_metadata_precedence(build_sbom: Callable[[str, dict[str, str]], str]) -> None:
    document: Final[dict[str, Any]] = json.loads(
        build_sbom(
            "pip/example.py",
            {
                "pip/_vendor/vendor.txt": "urllib3==1.26.4\n",
                "pip/_vendor/urllib3-1.26.4.dist-info/METADATA": "Name: urllib3\nVersion: 1.26.4\nLicense-Expression: MIT\n",
            },
        )
    )
    assert [child["licenses"] for child in document["components"][0]["components"] if child["type"] == "library"] == [
        [{"expression": "MIT", "acknowledgement": "declared"}],
    ]


@pytest.mark.parametrize(
    "requirement",
    [
        pytest.param("urllib3", id="missing"),
        pytest.param("urllib3>=1", id="range"),
        pytest.param("urllib3==1.*", id="wildcard"),
        pytest.param("urllib3 @ https://example.com/package.whl", id="url"),
    ],
)
def test_sbom_rejects_unpinned_vendor(build_sbom: Callable[[str, dict[str, str]], str], requirement: str) -> None:
    with pytest.raises(ValueError, match="Unpinned vendored dependency"):
        build_sbom("pip/example.py", {"pip/_vendor/vendor.txt": requirement})


@pytest.mark.parametrize(
    ("epoch", "expected"),
    [
        pytest.param(None, "2020-02-02T00:00:00+00:00", id="hatchling-default"),
        pytest.param("1700000000", "2023-11-14T22:13:20+00:00", id="source-date-epoch"),
    ],
)
def test_sbom_timestamp(
    build_sbom: Callable[[str, dict[str, str]], str], monkeypatch: pytest.MonkeyPatch, epoch: str | None, expected: str
) -> None:
    monkeypatch.delenv("SOURCE_DATE_EPOCH", raising=False)
    if epoch is not None:
        monkeypatch.setenv("SOURCE_DATE_EPOCH", epoch)
    assert json.loads(build_sbom("pip/example.py", {}))["metadata"]["timestamp"] == expected


def test_sbom_release_notes_from_project_url(build_sbom: Callable[[str, dict[str, str]], str]) -> None:
    root: Final[dict[str, Any]] = json.loads(build_sbom("pip/example.py", {}))["metadata"]["component"]
    assert [reference for reference in root["externalReferences"] if reference["type"] == "release-notes"] == [
        {"type": "release-notes", "url": "https://example.com/changelog", "comment": "Project-URL: Changelog"},
    ]


@pytest.mark.skipif(sys.version_info < (3, 10), reason="platform.freedesktop_os_release is new in Python 3.10")
def test_sbom_build_host_independent(
    build_sbom: Callable[[str, dict[str, str]], str],
    install_tool: Callable[[Path, str, bool, dict[str, bytes]], None],
    mocker: MockerFixture,
    tmp_path: Path,
) -> None:
    sboms: Final[list[str]] = []
    for host, extension, installer, sys_version in (
        (
            {
                "system": "Linux",
                "release": "6.17.0-1022-azure",
                "version": "#22~24.04.1-Ubuntu SMP",
                "machine": "x86_64",
                "platform": "Linux-6.17.0-1022-azure-x86_64-with-glibc2.39",
                "python_compiler": "GCC 13.3.0",
                "python_build": ("main", "Aug  5 2026 10:00:00"),
                "freedesktop_os_release": {"ID": "ubuntu", "VERSION_ID": "24.04"},
            },
            "cpython-314-x86_64-linux-gnu.so",
            b"uv\n",
            "3.14.7 (main, Aug  5 2026, 10:00:00) [GCC 13.3.0]",
        ),
        (
            {
                "system": "Linux",
                "release": "7.0.12-linuxkit",
                "version": "#1 SMP PREEMPT",
                "machine": "aarch64",
                "platform": "Linux-7.0.12-linuxkit-aarch64-with-glibc2.36",
                "python_compiler": "Clang 20.1.4",
                "python_build": ("main", "Sep  1 2026 08:00:00"),
                "freedesktop_os_release": {"ID": "debian", "VERSION_ID": "12"},
            },
            "cpython-314-aarch64-linux-gnu.so",
            b"pip\n",
            "3.14.7 (main, Sep  1 2026, 08:00:00) [Clang 20.1.4]",
        ),
    ):
        for name, value in host.items():
            mocker.patch(f"platform.{name}", autospec=True, return_value=value)
        mocker.patch.object(sys, "version", sys_version)
        install_tool(site := tmp_path / extension, "native", False, {f"native/_speedups.{extension}": b"\0"})
        install_tool(site, "pure", True, {"pure-1.0.dist-info/INSTALLER": installer})
        mocker.patch.object(sys, "path", [str(site), *sys.path])
        sboms.append(build_sbom("pip/example.py", {}))
        mocker.stopall()
    assert sboms[0] == sboms[1]


def test_sbom_ci_rerun(build_sbom: Callable[[str, dict[str, str]], str], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1700000000")
    monkeypatch.setenv("GITHUB_REPOSITORY", "downstream/project")
    monkeypatch.setenv("GITHUB_SHA", "a" * 40)
    monkeypatch.setenv("GITHUB_RUN_ID", "100")
    monkeypatch.setenv("GITHUB_RUN_ATTEMPT", "1")
    first: Final[str] = build_sbom("pip/example.py", {})
    monkeypatch.setenv("GITHUB_SHA", "b" * 40)
    monkeypatch.setenv("GITHUB_RUN_ID", "200")
    monkeypatch.setenv("GITHUB_RUN_ATTEMPT", "2")
    assert build_sbom("pip/example.py", {}) == first


def test_sbom_spdx_bundled_wheel(
    build_sbom: Callable[[str, dict[str, str]], str], render_spdx: Callable[[str], str]
) -> None:
    cyclonedx: Final[str] = build_sbom("pip/example.py", {})
    assert json.loads(render_spdx(cyclonedx))["packages"][1] == {
        "SPDXID": "SPDXRef-pkg-pypi-pip-1.0",
        "checksums": [
            {"algorithm": "SHA256", "checksumValue": json.loads(cyclonedx)["components"][0]["hashes"][0]["content"]}
        ],
        "comment": "virtualenv:bundled-wheel: src/virtualenv/seed/wheels/embed/pip-1.0-py3-none-any.whl\n"
        "virtualenv:seeded-for-python: 3.14",
        "downloadLocation": "NOASSERTION",
        "externalRefs": [
            {"referenceCategory": "PACKAGE-MANAGER", "referenceLocator": "pkg:pypi/pip@1.0", "referenceType": "purl"}
        ],
        "filesAnalyzed": False,
        "licenseConcluded": "NOASSERTION",
        "licenseDeclared": "NOASSERTION",
        "name": "pip",
        "primaryPackagePurpose": "LIBRARY",
        "versionInfo": "1.0",
    }


def test_sbom_spdx_relationships(
    build_sbom: Callable[[str, dict[str, str]], str], render_spdx: Callable[[str], str]
) -> None:
    rendered: Final[str] = render_spdx(build_sbom("pip/example.py", {"pip/_vendor/vendor.txt": "urllib3==1.26.4\n"}))
    assert [
        relationship
        for relationship in json.loads(rendered)["relationships"]
        if not relationship["spdxElementId"].startswith("SPDXRef-tool-")
    ] == [
        {
            "spdxElementId": "SPDXRef-DOCUMENT",
            "relationshipType": "DESCRIBES",
            "relatedSpdxElement": "SPDXRef-pkg-pypi-virtualenv-1.0",
        },
        {
            "spdxElementId": "SPDXRef-pkg-pypi-pip-1.0",
            "relationshipType": "CONTAINS",
            "relatedSpdxElement": "SPDXRef-pkg-pypi-pip-1.0-vendored-pkg-pypi-urllib3-1.26.4",
        },
        {
            "spdxElementId": "SPDXRef-pkg-pypi-virtualenv-1.0",
            "relationshipType": "DEPENDS_ON",
            "relatedSpdxElement": "SPDXRef-pkg-pypi-pip-1.0",
        },
        {
            "spdxElementId": "SPDXRef-pkg-pypi-virtualenv-1.0",
            "relationshipType": "DEPENDS_ON",
            "relatedSpdxElement": "SPDXRef-requires-dist-python-discovery-1.6",
        },
        {
            "spdxElementId": "SPDXRef-pkg-pypi-pip-1.0",
            "relationshipType": "DEPENDS_ON",
            "relatedSpdxElement": "SPDXRef-pkg-pypi-pip-1.0-vendored-pkg-pypi-urllib3-1.26.4",
        },
    ]


def test_sbom_spdx_build_tools(
    build_sbom: Callable[[str, dict[str, str]], str], render_spdx: Callable[[str], str]
) -> None:
    assert {
        relationship["relatedSpdxElement"]
        for relationship in json.loads(render_spdx(build_sbom("pip/example.py", {})))["relationships"]
        if relationship["relationshipType"] == "BUILD_TOOL_OF"
    } == {"SPDXRef-pkg-pypi-virtualenv-1.0"}


@pytest.mark.parametrize(
    ("metadata", "expected"),
    [
        pytest.param("License-Expression: MIT\n", ("MIT", None), id="expression"),
        pytest.param(
            "Classifier: License :: OSI Approved :: MIT License\nLicense: MIT\n",
            ("NOASSERTION", "Declared in package metadata as: MIT License; MIT"),
            id="names",
        ),
        pytest.param("", ("NOASSERTION", None), id="undeclared"),
    ],
)
def test_sbom_spdx_declared_license(
    build_sbom: Callable[[str, dict[str, str]], str],
    render_spdx: Callable[[str], str],
    metadata: str,
    expected: tuple[str, str | None],
) -> None:
    vendored: Final[dict[str, str]] = {
        "pip/_vendor/urllib3-1.26.4.dist-info/METADATA": f"Name: urllib3\nVersion: 1.26.4\n{metadata}"
    }
    assert [
        (package["licenseDeclared"], package.get("licenseComments"))
        for package in json.loads(render_spdx(build_sbom("pip/example.py", vendored)))["packages"]
        if package["name"] == "urllib3"
    ] == [expected]


def test_sbom_spdx_creation_info(
    build_sbom: Callable[[str, dict[str, str]], str],
    render_spdx: Callable[[str], str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1700000000")
    cyclonedx: Final[str] = build_sbom("pip/example.py", {})
    serial: Final[str] = json.loads(cyclonedx)["serialNumber"].removeprefix("urn:uuid:")
    assert (
        (document := json.loads(render_spdx(cyclonedx)))["documentNamespace"],
        document["creationInfo"]["created"],
    ) == (
        f"https://github.com/pypa/virtualenv/sboms/virtualenv-1.0-{serial}",
        "2023-11-14T22:13:20Z",
    )


def test_sbom_zipapp_components(zipapp_sbom: str) -> None:
    assert [
        (
            component["purl"],
            [prop["value"] for prop in component["properties"] if prop["name"].startswith("virtualenv:")],
            [child["name"] for child in component["components"]],
        )
        for component in json.loads(zipapp_sbom)["components"]
    ] == [
        (
            "pkg:pypi/virtualenv@1.0",
            [],
            ["virtualenv-1.0.dist-info/METADATA", "virtualenv/__init__.py", "pip"],
        ),
        (
            "pkg:pypi/distlib@0.4",
            ["__virtualenv__/distlib-0.4-py3-none-any", "3.14", "3.9"],
            [
                "__virtualenv__/distlib-0.4-py3-none-any/distlib-0.4.dist-info/METADATA",
                "__virtualenv__/distlib-0.4-py3-none-any/distlib/__init__.py",
            ],
        ),
    ]


def test_sbom_zipapp_embedded_wheel(zipapp: Path, zipapp_sbom: str) -> None:
    with zipfile.ZipFile(zipapp) as archive:
        digest: Final[str] = hashlib.sha256(
            archive.read("virtualenv/seed/wheels/embed/pip-1.0-py3-none-any.whl")
        ).hexdigest()
    assert json.loads(zipapp_sbom)["components"][0]["components"][2] == {
        "type": "library",
        "bom-ref": "pkg:pypi/pip@1.0",
        "name": "pip",
        "version": "1.0",
        "purl": "pkg:pypi/pip@1.0",
        "externalReferences": [],
        "hashes": [{"alg": "SHA-256", "content": digest}],
        "properties": [
            {"name": "virtualenv:bundled-wheel", "value": "virtualenv/seed/wheels/embed/pip-1.0-py3-none-any.whl"}
        ],
    }


def test_sbom_zipapp_loader_files(zipapp_sbom: str) -> None:
    assert [
        (component["name"], component["hashes"][0]["content"])
        for component in json.loads(zipapp_sbom)["metadata"]["component"]["components"]
    ] == [
        ("__main__.py", hashlib.sha256(b"# loader").hexdigest()),
        ("distributions.json", hashlib.sha256(_DISTRIBUTIONS.encode()).hexdigest()),
        ("modules.json", hashlib.sha256(b"{}").hexdigest()),
    ]


def test_sbom_zipapp_embeds_document(zipapp: Path, zipapp_sbom: str) -> None:
    with zipfile.ZipFile(zipapp) as archive:
        assert archive.read("virtualenv.pyz.cdx.json").decode("utf-8") == zipapp_sbom


@pytest.fixture
def zipapp(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    if sys.version_info < (3, 10):
        pytest.skip("zipfile.Path shares and then closes the handle of the archive it wraps before Python 3.10")
    wheel: Final[BytesIO] = BytesIO()
    with zipfile.ZipFile(wheel, "w") as archive:
        archive.writestr("pip-1.0.dist-info/METADATA", "Metadata-Version: 2.4\nName: pip\nVersion: 1.0\n")
    bundled: Final[str] = "__virtualenv__/distlib-0.4-py3-none-any"
    with zipfile.ZipFile(pyz := tmp_path / "virtualenv.pyz", "w") as archive:
        archive.writestr("__main__.py", "# loader")
        archive.writestr("modules.json", "{}")
        archive.writestr("distributions.json", _DISTRIBUTIONS)
        archive.writestr("virtualenv-1.0.dist-info/METADATA", "Metadata-Version: 2.4\nName: virtualenv\nVersion: 1.0\n")
        archive.writestr("virtualenv/__init__.py", "")
        archive.writestr("virtualenv/seed/wheels/embed/pip-1.0-py3-none-any.whl", wheel.getvalue())
        archive.writestr(
            f"{bundled}/distlib-0.4.dist-info/METADATA", "Metadata-Version: 2.4\nName: distlib\nVersion: 0.4\n"
        )
        archive.writestr(f"{bundled}/distlib/__init__.py", "")
    monkeypatch.syspath_prepend(str(Path(__file__).parents[2]))
    monkeypatch.setattr(sys, "argv", ["zipapp_sbom.py", str(pyz), str(tmp_path / "virtualenv.pyz.cdx.json")])
    runpy.run_path(str(Path(__file__).parents[2] / "tasks" / "zipapp_sbom.py"), run_name="__main__")
    return pyz


@pytest.fixture
def zipapp_sbom(zipapp: Path) -> str:
    return (zipapp.parent / "virtualenv.pyz.cdx.json").read_text(encoding="utf-8")


@pytest.fixture
def render_spdx(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Callable[[str], str]:
    def render(cyclonedx: str) -> str:
        (source := tmp_path / "virtualenv.cdx.json").write_text(cyclonedx, encoding="utf-8")
        monkeypatch.setattr(
            sys, "argv", ["cyclonedx_to_spdx.py", str(source), str(target := tmp_path / "out.spdx.json")]
        )
        runpy.run_path(str(Path(__file__).parents[2] / "tasks" / "cyclonedx_to_spdx.py"), run_name="__main__")
        return target.read_text(encoding="utf-8")

    return render


@pytest.fixture
def install_tool() -> Callable[[Path, str, bool, dict[str, bytes]], None]:
    def install(site: Path, name: str, purelib: bool, files: dict[str, bytes]) -> None:
        record: Final[StringIO] = StringIO(newline="")
        for path, content in files.items():
            (target := site / path).parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
            digest = base64.urlsafe_b64encode(hashlib.sha256(content).digest()).rstrip(b"=").decode()
            csv.writer(record).writerow((path, f"sha256={digest}", len(content)))
        (dist_info := site / f"{name}-1.0.dist-info").mkdir(exist_ok=True)
        (dist_info / "METADATA").write_text(f"Metadata-Version: 2.4\nName: {name}\nVersion: 1.0\n", encoding="utf-8")
        (dist_info / "WHEEL").write_text(
            f"Wheel-Version: 1.0\nRoot-Is-Purelib: {str(purelib).lower()}\n", encoding="utf-8"
        )
        (dist_info / "RECORD").write_text(record.getvalue(), encoding="utf-8", newline="")

    return install


@pytest.fixture
def build_sbom(tmp_path: Path) -> Callable[[str, dict[str, str]], str]:
    shutil.copyfile(Path(__file__).parents[2] / "hatch_build.py", tmp_path / "hatch_build.py")
    (tmp_path / "LICENSE").write_text("Copyright (c) example\n", encoding="utf-8")
    embed: Final[Path] = tmp_path / "src" / "virtualenv" / "seed" / "wheels" / "embed"
    embed.mkdir(parents=True)
    (embed / "__init__.py").write_text(
        'BUNDLE_SUPPORT = {"3.14": {"pip": "pip-1.0-py3-none-any.whl"}}\n', encoding="utf-8"
    )

    def build(filename: str, vendored_files: dict[str, str]) -> str:
        record: Final[StringIO] = StringIO(newline="")
        csv.writer(record).writerows([
            (filename, "sha256=ungWv48Bz-pBQUDeXa4iI7ADYaOWF3qctBD_YfIAFa0", "3"),
            ("pip-1.0.dist-info/RECORD", "", ""),
        ])
        with zipfile.ZipFile(embed / "pip-1.0-py3-none-any.whl", "w") as archive:
            for name, content in vendored_files.items():
                archive.writestr(zipfile.ZipInfo(name), content)
            archive.writestr(
                zipfile.ZipInfo("pip-1.0.dist-info/METADATA"), "Metadata-Version: 2.4\nName: pip\nVersion: 1.0\n"
            )
            archive.writestr(zipfile.ZipInfo("pip-1.0.dist-info/RECORD"), record.getvalue())
            archive.writestr(zipfile.ZipInfo(filename), b"abc")
        builder: Final[WheelBuilder] = WheelBuilder(
            str(tmp_path),
            config={
                "project": {
                    "name": "virtualenv",
                    "version": "1.0",
                    "description": "example",
                    "requires-python": ">=3.9",
                    "license": "MIT",
                    "maintainers": [{"name": "Example"}],
                    "dependencies": ["python-discovery>=1.6"],
                    "urls": {"Changelog": "https://example.com/changelog"},
                },
                "tool": {"hatch": {"build": {"hooks": {"custom": {"path": "hatch_build.py"}}}}},
            },
        )
        build_data: Final[dict[str, Any]] = builder.get_default_build_data()
        if "sbom_files" not in build_data:
            pytest.skip("Hatchling before 1.28 does not support SBOMs (Python 3.9 builds)")
        builder.get_build_hooks(str(tmp_path))["custom"].initialize("standard", build_data)
        return Path(build_data["sbom_files"][0]).read_text(encoding="utf-8")

    return build
