from __future__ import annotations

import base64
import csv
import hashlib
import json
import runpy
import shutil
import subprocess
import sys
import zipfile
from io import BytesIO, StringIO
from pathlib import Path
from typing import Any, Final

import pytest
from hatchling.builders.wheel import WheelBuilder

_ROOT: Final[Path] = Path(__file__).parents[2]
_EMBED: Final[str] = "virtualenv/seed/wheels/embed"
_LIBRARY: Final[str] = "__virtualenv__/distlib-0.4-py3-none-any"
_Document = dict[str, Any]
_DISTRIBUTIONS: Final[str] = json.dumps({
    "3.14": {"==any": {"distlib": f"{_LIBRARY}/distlib-0.4.dist-info"}},
    "3.9": {"==any": {"distlib": f"{_LIBRARY}/distlib-0.4.dist-info"}},
})
# the layout of src/virtualenv/seed/wheels/embed/catalog.py: another assignment comes before the table
_BUNDLE_TABLE: Final[str] = (
    "BUNDLE_FOLDER: Final[Path] = Path(__file__).absolute().parent\n"
    'BUNDLE_SUPPORT: Final[dict[str, dict[str, str]]] = {"3.14": {"pip": "pip-1.0-py3-none-any.whl"}}\n'
)


def test_sbom_seeded_for_python(wheel_sbom: _Document) -> None:
    assert wheel_sbom["components"][0]["properties"][:2] == [
        {"name": "virtualenv:bundled-wheel", "value": f"{_EMBED}/pip-1.0-py3-none-any.whl"},
        {"name": "virtualenv:seeded-for-python", "value": "3.14"},
    ]


def test_sbom_supplier(wheel_sbom: _Document) -> None:
    pypa = {"name": "Python Packaging Authority", "url": ["https://www.pypa.io"]}
    assert (wheel_sbom["metadata"]["supplier"], wheel_sbom["components"][0]["supplier"]) == (pypa, pypa)


def test_sbom_wheel_license_policy(wheel: Path, capfd: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit):
        validate_sbom(wheel.parent)
    assert f"bundled:{_EMBED}/pip-1.0-py3-none-any.whl: declares no license" in capfd.readouterr().err


def validate_sbom(target: Path) -> None:
    sys.path.insert(0, str(_ROOT / "tasks"))
    try:
        main = runpy.run_path(str(_ROOT / "tasks" / "validate_sbom.py"))["main"]
    finally:
        sys.path.remove(str(_ROOT / "tasks"))
    original = sys.argv
    sys.argv = ["validate_sbom.py", str(target)]
    try:
        main()
    finally:
        sys.argv = original


def test_sbom_zipapp_components(zipapp_sbom: _Document) -> None:
    assert [
        (component["bom-ref"], [child["name"] for child in component.get("components", [])])
        for component in zipapp_sbom["components"]
    ] == [
        (
            "pkg:pypi/virtualenv@1.0",
            [
                "virtualenv-1.0.dist-info/METADATA",
                "virtualenv/__init__.py",
                f"{_EMBED}/catalog.py",
                "pip",
            ],
        ),
        (
            f"bundled:{_LIBRARY}",
            [f"{_LIBRARY}/distlib-0.4.dist-info/METADATA", f"{_LIBRARY}/distlib/__init__.py"],
        ),
    ]


def test_sbom_zipapp_embedded_wheel_matches_wheel_sbom(zipapp_sbom: _Document, wheel_sbom: _Document) -> None:
    assert zipapp_sbom["components"][0]["components"][3] == wheel_sbom["components"][0]


def test_sbom_zipapp_loaded_for_python(zipapp_sbom: _Document) -> None:
    assert zipapp_sbom["components"][1]["properties"][:3] == [
        {"name": "virtualenv:bundled-wheel", "value": _LIBRARY},
        {"name": "virtualenv:loaded-for-python", "value": "3.14"},
        {"name": "virtualenv:loaded-for-python", "value": "3.9"},
    ]


def test_sbom_zipapp_loader_files(zipapp_sbom: _Document) -> None:
    assert [
        (component["name"], component["hashes"][0]["content"])
        for component in zipapp_sbom["metadata"]["component"]["components"]
    ] == [
        ("__main__.py", hashlib.sha256(b"# loader").hexdigest()),
        ("distributions.json", hashlib.sha256(_DISTRIBUTIONS.encode()).hexdigest()),
        ("modules.json", hashlib.sha256(b"{}").hexdigest()),
    ]


def test_sbom_zipapp_describes_every_file(zipapp: Path) -> None:
    assert describes_archive(zipapp) == []


def describes_archive(pyz: Path) -> list[str]:
    sys.path.insert(0, str(_ROOT / "tasks"))
    try:
        return runpy.run_path(str(_ROOT / "tasks" / "validate_sbom.py"))["describes_archive"](pyz)
    finally:
        sys.path.remove(str(_ROOT / "tasks"))


def test_sbom_zipapp_mismatch(tampered: Path) -> None:
    assert describes_archive(tampered) == [
        "virtualenv.pyz holds files the SBOM does not describe: ['extra.py']",
        "SBOM describes files virtualenv.pyz does not hold: ['modules.json']",
        "SHA-256 in the SBOM differs from the archive for: ['__main__.py']",
    ]


@pytest.fixture
def tampered(zipapp: Path, tmp_path: Path) -> Path:
    # the zipapp changed after its SBOM was written: a member dropped, one rewritten and one added
    with zipfile.ZipFile(zipapp) as source:
        members = {name: source.read(name) for name in source.namelist() if name != "modules.json"}
    members["__main__.py"] = b"# another loader"
    members["extra.py"] = b""
    (directory := tmp_path / "tampered").mkdir()
    with zipfile.ZipFile(target := directory / "virtualenv.pyz", "w") as archive:
        for name, content in members.items():
            archive.writestr(name, content)
    return target


def test_sbom_zipapp_mismatch_fails_validation(
    tampered: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    document_valid(monkeypatch)
    with pytest.raises(SystemExit, match="1"):
        validate_sbom(tampered)
    assert capsys.readouterr().out.splitlines()[0] == (
        "SBOM invalid: virtualenv.pyz holds files the SBOM does not describe: ['extra.py']"
    )


def document_valid(monkeypatch: pytest.MonkeyPatch) -> None:
    # python-sbom validate judges the document alone and passes here; what follows is the zipapp check. Patched once the
    # zipapp is built, since building it runs git through subprocess too
    monkeypatch.setattr(subprocess, "run", lambda command, **_: subprocess.CompletedProcess(command, 0))


def test_sbom_zipapp_matching_passes_validation(
    zipapp: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    document_valid(monkeypatch)
    validate_sbom(zipapp)
    assert not capsys.readouterr().out


def test_sbom_needs_one_wheel(tmp_path: Path) -> None:
    with pytest.raises(SystemExit, match=r"expected exactly one wheel in .*, found 0: \[\]"):
        validate_sbom(tmp_path)


def test_sbom_zipapp_license_problems(zipapp: Path, capfd: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit):
        validate_sbom(zipapp)
    errors = capfd.readouterr().err
    assert [
        problem in errors
        for problem in (
            "pkg:pypi/virtualenv@1.0: declares no license",
            f"bundled:{_EMBED}/pip-1.0-py3-none-any.whl: declares no license",
            f"bundled:{_LIBRARY}: declares no license",
        )
    ] == [True, True, True]


@pytest.fixture
def wheel(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.delenv("SOURCE_DATE_EPOCH", raising=False)
    project = tmp_path / "project"
    shutil.copytree(_ROOT / "tasks", project / "tasks", ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copyfile(_ROOT / "hatch_build.py", project / "hatch_build.py")
    (project / "LICENSE").write_text("Copyright (c) example\n", encoding="utf-8")
    (embed := project / "src" / _EMBED).mkdir(parents=True)
    (project / "src" / "virtualenv" / "__init__.py").write_text("", encoding="utf-8")
    (embed / "catalog.py").write_text(_BUNDLE_TABLE, encoding="utf-8")
    write_pip_wheel(
        embed / "pip-1.0-py3-none-any.whl",
        "Metadata-Version: 2.4\nName: pip\nVersion: 1.0\nProject-URL: Source, https://github.com/pypa/pip\n",
    )
    (project / "pyproject.toml").write_text(
        """\
[project]
name = "virtualenv"
version = "1.0"
license = "MIT"
license-files = ["LICENSE"]
urls.Source = "https://github.com/pypa/virtualenv"

[tool.hatch.build.targets.wheel]
packages = ["src/virtualenv"]

[tool.hatch.build.hooks.custom]
path = "hatch_build.py"

[tool.python-sbom]
supplier = { name = "Python Packaging Authority", url = ["https://www.pypa.io"] }
bundled-wheels = ["src/virtualenv/seed/wheels/embed/*.whl"]
content-provider = "tasks.sbom_content:VirtualenvContent"
""",
        encoding="utf-8",
    )
    builder: Final[WheelBuilder] = WheelBuilder(str(project))
    (built,) = builder.build(directory=str(tmp_path / "dist"), versions=["standard"])
    return Path(built)


def write_pip_wheel(target: Path | BytesIO, metadata: str) -> None:
    files: Final[dict[str, bytes]] = {"pip/example.py": b"abc", "pip-1.0.dist-info/METADATA": metadata.encode()}
    record: Final[StringIO] = StringIO(newline="")
    csv.writer(record).writerows([
        *(
            (name, f"sha256={base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b'=').decode()}", len(data))
            for name, data in files.items()
        ),
        ("pip-1.0.dist-info/RECORD", "", ""),
    ])
    with zipfile.ZipFile(target, "w") as archive:
        for name, data in {**files, "pip-1.0.dist-info/RECORD": record.getvalue().encode()}.items():
            archive.writestr(name, data)


@pytest.fixture
def wheel_sbom(wheel: Path) -> _Document:
    with zipfile.ZipFile(wheel) as archive:
        return json.loads(archive.read("virtualenv-1.0.dist-info/sboms/virtualenv.cdx.json"))


@pytest.fixture
def zipapp(tmp_path: Path, wheel: Path) -> Path:
    with zipfile.ZipFile(wheel) as built:
        pip = built.read(f"{_EMBED}/pip-1.0-py3-none-any.whl")
    with zipfile.ZipFile(pyz := tmp_path / "virtualenv.pyz", "w") as archive:
        archive.writestr("__main__.py", "# loader")
        archive.writestr("modules.json", "{}")
        archive.writestr("distributions.json", _DISTRIBUTIONS)
        archive.writestr("virtualenv-1.0.dist-info/METADATA", "Metadata-Version: 2.4\nName: virtualenv\nVersion: 1.0\n")
        archive.writestr("virtualenv/__init__.py", "")
        archive.writestr(f"{_EMBED}/catalog.py", _BUNDLE_TABLE)
        archive.writestr(f"{_EMBED}/pip-1.0-py3-none-any.whl", pip)
        archive.writestr(
            f"{_LIBRARY}/distlib-0.4.dist-info/METADATA", "Metadata-Version: 2.4\nName: distlib\nVersion: 0.4\n"
        )
        archive.writestr(f"{_LIBRARY}/distlib/__init__.py", "")
    # the project's options, provider and checkout are virtualenv's own, as in the zipapp release step
    subprocess.run(
        [
            sys.executable,
            "-m",
            "python_sbom",
            "archive",
            str(pyz),
            "--root",
            str(wheel.parents[1] / "project"),
            "--embed",
        ],
        check=True,
    )
    return pyz


@pytest.fixture
def zipapp_sbom(zipapp: Path) -> _Document:
    return json.loads(zipfile.ZipFile(zipapp).read("virtualenv.pyz.cdx.json"))
