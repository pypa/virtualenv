"""Helper script to rebuild virtualenv_support. Downloads the wheel files using pip."""

from __future__ import annotations

import ast
import hashlib
import os
import shutil
import subprocess
import sys
from collections import OrderedDict, defaultdict
from pathlib import Path
from tempfile import TemporaryDirectory
from textwrap import dedent
from threading import Thread
from typing import NoReturn

STRICT = "UPGRADE_ADVISORY" not in os.environ

BUNDLED = ["pip", "setuptools", "wheel"]
SUPPORT = [(3, i) for i in range(8, 17)]
DEST = Path(__file__).resolve().parents[1] / "src" / "virtualenv" / "seed" / "wheels" / "embed"


def run() -> NoReturn:
    if "--regen" in sys.argv[1:]:
        render_init()
        raise SystemExit(0)
    old_batch = {i.name for i in DEST.iterdir() if i.suffix == ".whl"}
    with TemporaryDirectory() as temp:
        folders = _download_all(Path(temp))
        new_batch = {i.name: i for f in folders for i in Path(f).iterdir()}
        new_packages = new_batch.keys() - old_batch
        remove_packages = old_batch - new_batch.keys()
        _sync_dest(new_packages, remove_packages, new_batch)
        added = collect_package_versions(new_packages)
        removed = collect_package_versions(remove_packages)
        outcome = (1 if STRICT else 0) if (added or removed) else 0
        print(f"Outcome {outcome} added {added} removed {removed}")  # noqa: T201
        _write_changelog(added, removed)
        render_init(folders=folders)
        raise SystemExit(outcome)


def _download_all(temp_path: Path) -> dict[Path, str]:
    folders: dict[Path, str] = {}
    targets: list[Thread] = []
    for support in SUPPORT:
        support_ver = ".".join(str(i) for i in support)
        into = temp_path / support_ver
        into.mkdir()
        folders[into] = support_ver
        for package in BUNDLED:
            if package == "wheel" and support >= (3, 9):
                continue
            thread = Thread(target=download, args=(support_ver, str(into), package))
            targets.append(thread)
            thread.start()
    for thread in targets:
        thread.join()
    return folders


def _sync_dest(new_packages: set[str], remove_packages: set[str], new_batch: dict[str, Path]) -> None:
    for package in remove_packages:
        (DEST / package).unlink()
    for package in new_packages:
        shutil.copy2(str(new_batch[package]), DEST / package)


def _write_changelog(added: dict[str, list[str]], removed: dict[str, list[str]]) -> None:
    lines = ["Upgrade embedded wheels:", ""]
    for key, versions in added.items():
        text = f"* {key} to {fmt_version(versions)}"
        if key in removed:
            rem = ", ".join(f"``{i}``" for i in removed[key])
            text += f" from {rem}"
            del removed[key]
        lines.append(text)
    for key, versions in removed.items():
        lines.append(f"Removed {key} of {fmt_version(versions)}")
    lines.append("")
    changelog = "\n".join(lines)
    print(changelog)  # noqa: T201
    if len(lines) >= 4:  # noqa: PLR2004
        (Path(__file__).parents[1] / "docs" / "changelog" / "u.bugfix.rst").write_text(changelog, encoding="utf-8")


def render_init(folders: dict[Path, str] | None = None) -> None:
    """Write ``embed/__init__.py`` from the wheels currently in DEST.

    When called from ``run()`` after a download round, ``folders`` maps each per-python-version temp folder to its
    version string, which is how support for a wheel is determined. When called with ``--regen`` there are no downloaded
    folders — the existing ``BUNDLE_SUPPORT`` from the current ``__init__.py`` is used so regeneration is deterministic.

    """
    if folders is None:
        support_table = _support_table_from_existing_init()
    else:
        present = {i.name: i for f in folders for i in Path(f).iterdir() if i.suffix == ".whl"}
        support_table = OrderedDict((".".join(str(j) for j in i), []) for i in SUPPORT)
        for package in sorted(present):
            for folder, version in sorted(folders.items()):
                if (folder / package).exists():
                    support_table[version].append(package)
        support_table = OrderedDict((k, OrderedDict((i.split("-")[0], i) for i in v)) for k, v in support_table.items())
    wheel_names = sorted({wheel for mapping in support_table.values() for wheel in mapping.values()})
    sha_table = OrderedDict((name, _sha256(DEST / name)) for name in wheel_names)
    nl = "\n"
    bundle = "".join(
        f"\n        {v!r}: {{{nl}{''.join(f'            {p!r}: {f!r},{nl}' for p, f in line.items())}        }},"
        for v, line in support_table.items()
    )
    sha_block = "".join(f"\n        {name!r}: {digest!r}," for name, digest in sha_table.items())
    msg = dedent(
        f"""
    from __future__ import annotations

    import hashlib
    import zipfile
    from pathlib import Path

    from virtualenv.info import IS_ZIPAPP, ROOT
    from virtualenv.seed.wheels.util import Wheel

    BUNDLE_FOLDER = Path(__file__).absolute().parent
    BUNDLE_SUPPORT = {{ {bundle} }}
    MAX = next(reversed(BUNDLE_SUPPORT))

    # SHA-256 of every bundled wheel. Verified on load so a corrupted or tampered wheel on disk fails loud instead of
    # being handed to pip. Generated together with ``BUNDLE_SUPPORT`` by ``tasks/upgrade_wheels.py``.
    BUNDLE_SHA256 = {{ {sha_block} }}

    _VERIFIED_WHEELS: set[str] = set()


    def get_embed_wheel(distribution: str, for_py_version: str) -> Wheel | None:
        \"\"\"Return the bundled wheel that ships with virtualenv for a given distribution and Python version.

        :param distribution: project name of the seed package, for example ``pip`` or ``setuptools``.
        :param for_py_version: major.minor Python version string the environment will be created for.

        :returns: a :class:`Wheel` pointing at the verified bundled file, or ``None`` when no wheel is bundled for the
            requested combination.

        :raises RuntimeError: if the bundled wheel on disk fails SHA-256 verification.

        \"\"\"
        mapping = BUNDLE_SUPPORT.get(for_py_version, {{}}) or BUNDLE_SUPPORT[MAX]
        wheel_file = mapping.get(distribution)
        if wheel_file is None:
            return None
        path = BUNDLE_FOLDER / wheel_file
        _verify_bundled_wheel(path)
        return Wheel.from_path(path)


    def _verify_bundled_wheel(path: Path) -> None:
        name = path.name
        if name in _VERIFIED_WHEELS:
            return
        expected = BUNDLE_SHA256.get(name)
        if expected is None:
            msg = f"bundled wheel {{name}} has no recorded sha256 in BUNDLE_SHA256"
            raise RuntimeError(msg)
        actual = _hash_bundled_wheel(path)
        if actual != expected:
            msg = f"bundled wheel {{name}} sha256 mismatch: expected {{expected}}, got {{actual}}"
            raise RuntimeError(msg)
        _VERIFIED_WHEELS.add(name)


    def _hash_bundled_wheel(path: Path) -> str:
        # ``path`` is under the package directory; when virtualenv runs from a zipapp the wheel lives inside the
        # archive and cannot be opened as a regular file, so read the bytes straight from the zipapp entry.
        digest = hashlib.sha256()
        if IS_ZIPAPP:
            entry = path.resolve().relative_to(Path(ROOT).resolve()).as_posix()
            with zipfile.ZipFile(ROOT, "r") as archive, archive.open(entry) as stream:
                for chunk in iter(lambda: stream.read(1 << 20), b""):
                    digest.update(chunk)
        else:
            with path.open("rb") as stream:
                for chunk in iter(lambda: stream.read(1 << 20), b""):
                    digest.update(chunk)
        return digest.hexdigest()


    __all__ = [
        "BUNDLE_FOLDER",
        "BUNDLE_SHA256",
        "BUNDLE_SUPPORT",
        "MAX",
        "get_embed_wheel",
    ]

    """,
    )
    dest_target = DEST / "__init__.py"
    dest_target.write_text(msg, encoding="utf-8")
    subprocess.run([sys.executable, "-m", "ruff", "check", str(dest_target), "--fix", "--unsafe-fixes"], check=False)
    subprocess.run([sys.executable, "-m", "ruff", "format", str(dest_target), "--preview"], check=False)


def _support_table_from_existing_init() -> OrderedDict[str, OrderedDict[str, str]]:
    source = (DEST / "__init__.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "BUNDLE_SUPPORT" for t in node.targets
        ):
            bundle_support = ast.literal_eval(node.value)
            return OrderedDict(
                (version, OrderedDict(sorted(mapping.items()))) for version, mapping in bundle_support.items()
            )
    msg = f"BUNDLE_SUPPORT not found in {DEST / '__init__.py'}"
    raise RuntimeError(msg)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fmt_version(versions: list[str]) -> str:
    return ", ".join(f"``{v}``" for v in versions)


def collect_package_versions(new_packages: set[str]) -> dict[str, list[str]]:
    result = defaultdict(list)
    for package in new_packages:
        split = package.split("-")
        if len(split) < 2:  # noqa: PLR2004
            raise ValueError(package)
        key, version = split[0:2]
        result[key].append(version)
    return result


def download(python_version: str, dest: str, package: str) -> None:
    subprocess.call(
        [
            sys.executable,
            "-W",
            "ignore::EncodingWarning",
            "-m",
            "pip",
            "--disable-pip-version-check",
            "download",
            "--no-cache-dir",
            "--only-binary=:all:",
            "--python-version",
            python_version,
            "-d",
            dest,
            package,
        ],
    )


if __name__ == "__main__":
    run()
