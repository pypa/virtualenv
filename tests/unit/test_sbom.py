from __future__ import annotations

import csv
import json
import shutil
import zipfile
from io import StringIO
from pathlib import Path
from typing import TYPE_CHECKING, Final

import pytest
from hatchling.builders.wheel import WheelBuilder

if TYPE_CHECKING:
    from collections.abc import Callable

    from pytest_mock import MockerFixture


@pytest.fixture
def vendored_files() -> dict[str, str]:
    return {}


@pytest.fixture
def build_sbom(tmp_path: Path, vendored_files: dict[str, str]) -> Callable[[str], str]:
    shutil.copyfile(Path(__file__).parents[2] / "hatch_build.py", tmp_path / "hatch_build.py")
    (tmp_path / "LICENSE").write_text("Copyright (c) example\n", encoding="utf-8")
    embed: Final[Path] = tmp_path / "src" / "virtualenv" / "seed" / "wheels" / "embed"
    embed.mkdir(parents=True)
    (embed / "__init__.py").write_text(
        'BUNDLE_SUPPORT = {"3.14": {"pip": "pip-1.0-py3-none-any.whl"}}\n', encoding="utf-8"
    )

    def build(filename: str) -> str:
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
                },
                "tool": {"hatch": {"build": {"hooks": {"custom": {"path": "hatch_build.py"}}}}},
            },
        )
        build_data: Final = builder.get_default_build_data()
        if "sbom_files" not in build_data:
            pytest.skip("Hatchling before 1.28 does not support SBOMs (Python 3.9 builds)")
        builder.get_build_hooks(str(tmp_path))["custom"].initialize("standard", build_data)
        return Path(build_data["sbom_files"][0]).read_text(encoding="utf-8")

    return build


@pytest.mark.parametrize(
    "filename",
    [
        pytest.param("pip/example.py", id="plain"),
        pytest.param("pip/a,b.py", id="comma"),
        pytest.param('pip/a"b.py', id="quote"),
        pytest.param("pip/a\nb.py", id="newline"),
    ],
)
def test_sbom_record_paths(build_sbom: Callable[[str], str], filename: str) -> None:
    document = json.loads(build_sbom(filename))
    assert document["components"][0]["components"] == [
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


def test_sbom_unresolved_dependencies(build_sbom: Callable[[str], str]) -> None:
    document = json.loads(build_sbom("pip/example.py"))
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
def test_sbom_vendored_identity(
    build_sbom: Callable[[str], str], vendored_files: dict[str, str], source: str, content: str
) -> None:
    vendored_files[source] = content
    document: Final = json.loads(build_sbom("pip/example.py"))
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


def test_sbom_vendored_relationship(build_sbom: Callable[[str], str], vendored_files: dict[str, str]) -> None:
    vendored_files["pip/_vendor/vendor.txt"] = "urllib3==1.26.4\n"
    document: Final = json.loads(build_sbom("pip/example.py"))
    assert [entry for entry in document["dependencies"] if not entry["ref"].startswith("tool:")] == [
        {"ref": "pkg:pypi/virtualenv@1.0", "dependsOn": ["pkg:pypi/pip@1.0", "requires-dist:python-discovery>=1.6"]},
        {"ref": "pkg:pypi/pip@1.0", "dependsOn": ["pkg:pypi/pip@1.0#vendored/pkg:pypi/urllib3@1.26.4"]},
    ]


def test_sbom_vendored_metadata_precedence(build_sbom: Callable[[str], str], vendored_files: dict[str, str]) -> None:
    vendored_files.update({
        "pip/_vendor/vendor.txt": "urllib3==1.26.4\n",
        "pip/_vendor/urllib3-1.26.4.dist-info/METADATA": "Name: urllib3\nVersion: 1.26.4\nLicense-Expression: MIT\n",
    })
    document: Final = json.loads(build_sbom("pip/example.py"))
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
def test_sbom_rejects_unpinned_vendor(
    build_sbom: Callable[[str], str], vendored_files: dict[str, str], requirement: str
) -> None:
    vendored_files["pip/_vendor/vendor.txt"] = requirement
    with pytest.raises(ValueError, match="Unpinned vendored dependency"):
        build_sbom("pip/example.py")


@pytest.mark.parametrize(
    ("epoch", "expected"),
    [
        pytest.param(None, "2020-02-02T00:00:00+00:00", id="hatchling-default"),
        pytest.param("1700000000", "2023-11-14T22:13:20+00:00", id="source-date-epoch"),
    ],
)
def test_sbom_timestamp(
    build_sbom: Callable[[str], str], monkeypatch: pytest.MonkeyPatch, epoch: str | None, expected: str
) -> None:
    monkeypatch.delenv("SOURCE_DATE_EPOCH", raising=False)
    if epoch is not None:
        monkeypatch.setenv("SOURCE_DATE_EPOCH", epoch)
    assert json.loads(build_sbom("pip/example.py"))["metadata"]["timestamp"] == expected


@pytest.mark.parametrize(
    ("build", "expected"),
    [
        pytest.param(("main", "Sep 21 2026"), "main Sep 21 2026", id="complete"),
        pytest.param(("main", None), "main", id="graalpy-missing-date"),
        pytest.param(("main", ""), "main", id="empty-date"),
    ],
)
def test_sbom_python_build(
    build_sbom: Callable[[str], str], mocker: MockerFixture, build: tuple[str, str | None], expected: str
) -> None:
    mocker.patch("platform.python_build", autospec=True, return_value=build)
    document: Final = json.loads(build_sbom("pip/example.py"))
    assert [
        prop["value"]
        for component in document["metadata"]["tools"]["components"]
        for prop in component.get("properties", [])
        if prop["name"] == "python:build"
    ] == [expected]


def test_sbom_ci_rerun(build_sbom: Callable[[str], str], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1700000000")
    monkeypatch.setenv("GITHUB_REPOSITORY", "downstream/project")
    monkeypatch.setenv("GITHUB_SHA", "a" * 40)
    monkeypatch.setenv("GITHUB_RUN_ID", "100")
    monkeypatch.setenv("GITHUB_RUN_ATTEMPT", "1")
    first: Final[str] = build_sbom("pip/example.py")
    monkeypatch.setenv("GITHUB_SHA", "b" * 40)
    monkeypatch.setenv("GITHUB_RUN_ID", "200")
    monkeypatch.setenv("GITHUB_RUN_ATTEMPT", "2")
    assert build_sbom("pip/example.py") == first
