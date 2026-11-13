"""Helper script to rebuild virtualenv_support. Downloads the wheel files using pip."""

from __future__ import annotations

import ast
import hashlib
import os
import shutil
import subprocess
import sys
import zipfile
from collections import OrderedDict, defaultdict
from pathlib import Path
from tempfile import TemporaryDirectory
from textwrap import dedent
from threading import Thread
from typing import Final, NoReturn

from virtualenv.util.path import write_file

_STRICT: Final[bool] = "UPGRADE_ADVISORY" not in os.environ

_SUPPORT: Final[tuple[tuple[int, int], ...]] = tuple((3, i) for i in range(9, 17))
_DEST: Final[Path] = Path(__file__).resolve().parents[1] / "src" / "virtualenv" / "seed" / "wheels" / "embed"
_NOTICES_DEST: Final[Path] = Path(__file__).resolve().parents[1] / "THIRD-PARTY-NOTICES.md"


def run() -> NoReturn:
    if "--regen" in sys.argv[1:]:
        render_init()
        render_notices()
        raise SystemExit(0)
    old_batch = {i.name for i in _DEST.iterdir() if i.suffix == ".whl"}
    with TemporaryDirectory() as temp:
        folders = _download_all(Path(temp))
        new_batch = {i.name: i for f in folders for i in Path(f).iterdir()}
        new_packages = new_batch.keys() - old_batch
        remove_packages = old_batch - new_batch.keys()
        for package in remove_packages:
            (_DEST / package).unlink()
        for package in new_packages:
            shutil.copy2(str(new_batch[package]), _DEST / package)
        added = collect_package_versions(new_packages)
        removed = collect_package_versions(remove_packages)
        outcome = (1 if _STRICT else 0) if (added or removed) else 0
        # the upgrade summary is printed for the developer running the task
        print(f"Outcome {outcome} added {added} removed {removed}")  # ruff:ignore[print]
        _write_changelog(added, removed)
        render_init(folders=folders)
        render_notices()
        raise SystemExit(outcome)


def _download_all(temp_path: Path) -> dict[Path, str]:
    folders: dict[Path, str] = {}
    targets: list[Thread] = []
    bundled = ["pip", "setuptools"]
    for support in _SUPPORT:
        support_ver = ".".join(str(i) for i in support)
        into = temp_path / support_ver
        into.mkdir()
        folders[into] = support_ver
        for package in bundled:
            thread = Thread(target=download, args=(support_ver, str(into), package))
            targets.append(thread)
            thread.start()
    for thread in targets:
        thread.join()
    return folders


def _write_changelog(added: dict[str, list[str]], removed: dict[str, list[str]]) -> None:
    if not added and not removed:
        return
    # towncrier wraps a fragment in its own list item, so the fragment must be a prose paragraph, not a bullet list
    sentences: list[str] = []
    if added:
        upgrades = [
            f"{key} to {fmt_version(versions)}{f' from {fmt_version(removed[key])}' if key in removed else ''}"
            for key, versions in added.items()
        ]
        sentences.append(f"Upgrade embedded wheels: {', '.join(upgrades)}.")
    sentences.extend(
        f"Removed {key} of {fmt_version(versions)}." for key, versions in removed.items() if key not in added
    )
    changelog = " ".join(sentences)
    print(changelog)  # ruff:ignore[print]  # the changelog is the command's output
    fragment: Final[Path] = Path(__file__).parents[1] / "docs" / "changelog" / "embedded-wheels.bugfix.rst"
    fragment.parent.mkdir(parents=True, exist_ok=True)
    write_file(fragment, f"{changelog}\n".encode())


def render_init(folders: dict[Path, str] | None = None) -> None:
    # Write ``embed/__init__.py`` from the wheels currently in DEST.
    #
    # When called from ``run()`` after a download round, ``folders`` maps each per-python-version temp folder to its
    # version string, which is how support for a wheel is determined. When called with ``--regen`` there are no
    # downloaded folders — the existing ``BUNDLE_SUPPORT`` from the current ``__init__.py`` is used so regeneration is
    # deterministic.
    if folders is None:
        support_table = _support_table_from_existing_init()
    else:
        present = {i.name: i for f in folders for i in Path(f).iterdir() if i.suffix == ".whl"}
        support_table = OrderedDict((".".join(str(j) for j in i), []) for i in _SUPPORT)
        for package in sorted(present):
            for folder, version in sorted(folders.items()):
                if (folder / package).exists():
                    support_table[version].append(package)
        support_table = OrderedDict((k, OrderedDict((i.split("-")[0], i) for i in v)) for k, v in support_table.items())
    wheel_names = sorted({wheel for mapping in support_table.values() for wheel in mapping.values()})
    sha_table = OrderedDict((name, _sha256(_DEST / name)) for name in wheel_names)
    nl = "\n"
    bundle = "".join(
        f"\n        {v!r}: {{{nl}{''.join(f'            {p!r}: {f!r},{nl}' for p, f in line.items())}        }},"
        for v, line in support_table.items()
    )
    sha_block = "".join(f"\n        {name!r}: {digest!r}," for name, digest in sha_table.items())
    msg = dedent(
        f"""
    from __future__ import annotations

    import hashlib  # simplint: ignore[init-module-content]  # preserve API module
    import zipfile  # simplint: ignore[init-module-content]  # preserve API module
    from pathlib import Path  # simplint: ignore[init-module-content]  # preserve API module
    from typing import Final  # simplint: ignore[init-module-content]  # preserve API module

    from virtualenv.info import IS_ZIPAPP, ROOT  # simplint: ignore[init-module-content]  # preserve API module
    from virtualenv.seed.wheels.util import Wheel  # simplint: ignore[init-module-content]  # preserve API module

    #: The folder holding the bundled seed wheels.
    BUNDLE_FOLDER: Final[Path] = Path(__file__).absolute().parent
    #: The bundled wheel file names, keyed by the Python version they support, then by distribution.
    BUNDLE_SUPPORT: Final[dict[str, dict[str, str]]] = {{ {bundle} }}
    #: The newest Python version with bundled wheels.
    MAX: Final[str] = next(reversed(BUNDLE_SUPPORT))
    #: The oldest Python version with bundled wheels.
    MIN: Final[str] = next(iter(BUNDLE_SUPPORT))


    def _release_tuple(version: str) -> tuple[int, ...]:
        return tuple(int(part) for part in version.split("."))


    # oldest target Python version virtualenv still bundles seed wheels for; anything below this has no embedded pip
    #: The oldest Python version bundled wheels support, as a release tuple.
    OLDEST_SUPPORTED: Final[tuple[int, ...]] = _release_tuple(MIN)

    # SHA-256 of every bundled wheel. Verified on load so a corrupted or tampered wheel on disk fails loud instead of
    # being handed to pip. Generated together with ``BUNDLE_SUPPORT`` by ``tasks/upgrade_wheels.py``.
    #: The SHA-256 digest of each bundled wheel file, keyed by file name.
    BUNDLE_SHA256: Final[dict[str, str]] = {{ {sha_block} }}

    _VERIFIED_WHEELS: Final[set[str]] = set()


    def get_embed_wheel(distribution: str, for_py_version: str | None) -> Wheel | None:
        \"\"\"Return the bundled wheel that ships with virtualenv for a given distribution and Python version.

        :param distribution: project name of the seed package, for example ``pip`` or ``setuptools``.
        :param for_py_version: major.minor Python version string the environment will be created for, or ``None`` to use the
            newest bundle.

        :returns: a :class:`Wheel` pointing at the verified bundled file, or ``None`` when no wheel is bundled for the
            requested combination, including target versions below the oldest bundled one.

        :raises RuntimeError: if the bundled wheel on disk fails SHA-256 verification.

        \"\"\"
        if for_py_version is None or _release_tuple(for_py_version) > _release_tuple(MAX):
            # no specific target, or a Python newer than anything bundled: reuse the newest bundle
            mapping = BUNDLE_SUPPORT[MAX]
        else:  # versions below the oldest bundled one fall through to None instead of an incompatible newer wheel
            mapping = BUNDLE_SUPPORT.get(for_py_version)
        if not mapping:
            return None
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
        if (actual := _hash_bundled_wheel(path)) != expected:
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
        "MIN",
        "OLDEST_SUPPORTED",
        "get_embed_wheel",
    ]

    """,
    )
    dest_target = _DEST / "__init__.py"
    dest_target.write_text(msg, encoding="utf-8")
    subprocess.run([sys.executable, "-m", "ruff", "check", str(dest_target), "--fix", "--unsafe-fixes"], check=False)
    subprocess.run([sys.executable, "-m", "ruff", "format", str(dest_target), "--preview"], check=False)


def render_notices() -> None:
    # Write ``THIRD-PARTY-NOTICES.md`` from the wheels currently bundled in DEST.
    #
    # Reads the ``BUNDLE_SHA256`` table ``render_init`` just wrote, so the notices always match what is actually
    # bundled.
    # Only the license of the wheel virtualenv itself redistributes is reproduced here - whatever that wheel in turn
    # vendors (pip's own ``_vendor`` tree, for example) already carries its license inside the wheel and stays there
    # rather than being duplicated at the top level.
    tree = ast.parse((_DEST / "__init__.py").read_text(encoding="utf-8"))
    wheel_names: list[str] = []
    for node in tree.body:
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == "BUNDLE_SHA256":
            wheel_names = sorted(ast.literal_eval(node.value))
            break
    groups: dict[tuple[str, str], list[str]] = defaultdict(list)
    for wheel_name in wheel_names:
        distribution = wheel_name.split("-")[0]
        groups[distribution, _wheel_license_text(_DEST / wheel_name)].append(wheel_name)
    sections = []
    for (distribution, text), names in sorted(groups.items()):
        filenames = ", ".join(f"``{name}``" for name in sorted(names))
        sections.append(
            f"## {distribution}\n\nBundled as: {filenames}\n\n"
            f"Upstream: https://pypi.org/project/{distribution}/\n\n"
            f"```\n{text.strip()}\n```\n"
        )
    header = dedent("""\
        <!-- Generated by tasks/upgrade_wheels.py; do not edit by hand. -->
        # Third-party notices

        virtualenv is distributed under the MIT License, see `LICENSE`. The wheels under
        `src/virtualenv/seed/wheels/embed/` are redistributed unmodified and remain under their own licenses,
        reproduced below. Each wheel also carries its own license text inside its `.dist-info/licenses/`
        directory, including the licenses of anything it in turn vendors.

        """)
    write_file(_NOTICES_DEST, (header + "\n".join(sections)).encode("utf-8"))
    if (pre_commit := shutil.which("pre-commit")) is None:
        msg = "pre-commit must be installed to format THIRD-PARTY-NOTICES.md"
        raise RuntimeError(msg)
    command = [pre_commit, "run", "mdformat", "--files", str(_NOTICES_DEST)]
    subprocess.run(command, check=False)
    subprocess.run(command, check=True)


def _wheel_license_text(path: Path) -> str:
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        prefix = f"{next(name.split('/', 1)[0] for name in names if name.endswith('.dist-info/METADATA'))}/licenses/"
        # top-level files only: a nested match would be a license belonging to something the wheel itself vendors
        candidates = sorted(
            name
            for name in names
            if name.startswith(prefix) and "/" not in name[len(prefix) :] and "LICENSE" in Path(name).name.upper()
        )
        if not candidates:
            msg = f"no top-level license file found under {prefix} in {path.name}"
            raise RuntimeError(msg)
        return archive.read(candidates[0]).decode("utf-8")


def _support_table_from_existing_init() -> OrderedDict[str, OrderedDict[str, str]]:
    for node in ast.parse((_DEST / "__init__.py").read_text(encoding="utf-8")).body:
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == "BUNDLE_SUPPORT":
            bundle_support = ast.literal_eval(node.value)
            return OrderedDict(
                (version, OrderedDict(sorted(mapping.items()))) for version, mapping in bundle_support.items()
            )
    msg = f"BUNDLE_SUPPORT not found in {_DEST / '__init__.py'}"
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
        # a package name needs a dash to split off its version, 2 is that field count
        if len(split) < 2:  # ruff:ignore[magic-value-comparison]
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
