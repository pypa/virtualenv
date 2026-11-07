"""https://docs.python.org/3/library/zipapp.html."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import zipapp
import zipfile
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING, Final

from packaging.markers import Marker

from tasks.fetch_url import fetch

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

if TYPE_CHECKING:
    from typing import TypedDict

    from typing_extensions import NotRequired

    class LockedWheel(TypedDict):
        url: str
        hashes: dict[str, str]

    class LockedPackage(TypedDict):
        name: str
        version: str
        marker: NotRequired[str]
        wheels: NotRequired[list[LockedWheel]]


_HERE: Final[Path] = Path(__file__).parent.absolute()

_VERSIONS: Final[tuple[str, ...]] = tuple(f"3.{i}" for i in range(15, 8, -1))
_LOCK: Final[Path] = _HERE.parent / "pylock.zipapp.toml"
_PLATFORMS: Final[tuple[str, ...]] = ("darwin", "linux", "win32")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dest", default="virtualenv.pyz")
    parser.add_argument("--wheel-dir", type=Path, help="bundle the virtualenv wheel from here instead of building one")
    args = parser.parse_args()
    with TemporaryDirectory() as folder:
        _create_zipapp(os.path.abspath(args.dest), _get_wheels_for_support_versions(Path(folder), args.wheel_dir))


def _get_wheels_for_support_versions(
    folder: Path, wheel_dir: Path | None
) -> dict[str, dict[str, dict[str, WheelForVersion]]]:
    packages: defaultdict[str, dict[str, dict[str, WheelForVersion]]] = defaultdict(lambda: {"==any": {}})
    wheel = _build_virtualenv_wheel(folder) if wheel_dir is None else next(wheel_dir.glob("virtualenv-*.whl"))
    packages["virtualenv"]["==any"][wheel.name] = WheelForVersion(wheel, list(_VERSIONS))
    for package in tomllib.loads(_LOCK.read_text(encoding="utf-8"))["packages"]:
        if not (versions := python_versions_for(package)):
            continue
        wheel = _download_locked_wheel(package, folder)
        packages[package["name"]]["==any"][wheel.name] = WheelForVersion(wheel, versions)
    for name, platforms in packages.items():
        for wheel_name, wheel_for_version in platforms["==any"].items():
            sys.stdout.write(f"{name}: {wheel_name} for {' '.join(wheel_for_version.versions)}\n")
    return packages


def _build_virtualenv_wheel(into: Path) -> Path:
    with TemporaryDirectory() as temp_folder:
        # pip does not guarantee building from the same source tree in parallel is safe, so build from a copy
        source = Path(temp_folder) / _HERE.parent.name
        shutil.copytree(
            _HERE.parent, source, ignore=shutil.ignore_patterns(".tox", ".tox4", "venv", "__pycache__", "*.pyz")
        )
        subprocess.run(
            [sys.executable, "-m", "pip", "wheel", "-q", "--no-deps", "-w", str(into), str(source)], check=True
        )
    return next(into.glob("virtualenv-*.whl"))


def _download_locked_wheel(package: LockedPackage, into: Path) -> Path:
    # the zipapp cannot load compiled extensions, so only a pure-Python wheel can be bundled
    if not (wheels := [wheel for wheel in package.get("wheels", []) if wheel["url"].endswith("-none-any.whl")]):
        msg = f"{_LOCK.name} has no pure-Python wheel for {package['name']} {package['version']}"
        raise RuntimeError(msg)
    url, expected = wheels[0]["url"], wheels[0]["hashes"]["sha256"]
    if (actual := hashlib.sha256(content := fetch(url)).hexdigest()) != expected:
        msg = f"{url} has sha256 {actual}, but {_LOCK.name} records {expected}"
        raise RuntimeError(msg)
    (dest := into / url.rsplit("/", 1)[1]).write_bytes(content)
    return dest


def python_versions_for(package: LockedPackage) -> list[str]:
    if (marker := package.get("marker")) is None:
        return list(_VERSIONS)
    parsed, versions = Marker(marker), []
    for version in _VERSIONS:
        environment = {"python_version": version, "python_full_version": f"{version}.0"}
        # every bundled wheel is keyed as ==any, so a marker that differs per platform would ship the build host's pick
        if (
            len(
                matches := {
                    parsed.evaluate(
                        {**environment, "sys_platform": platform, "dependency_groups": {"project-runtime"}},
                        context="lock_file",
                    )
                    for platform in _PLATFORMS
                }
            )
            != 1
        ):
            msg = (
                f"{_LOCK.name} marks {package['name']} as platform specific ({marker}), which the zipapp cannot select"
            )
            raise RuntimeError(msg)
        if matches.pop():
            versions.append(version)
    return versions


@dataclass(frozen=True)
class WheelForVersion:
    wheel: Path
    versions: list[str]


def _create_zipapp(dest: str, packages: dict[str, dict[str, dict[str, WheelForVersion]]]) -> None:
    bio = io.BytesIO()
    base = PurePosixPath("__virtualenv__")
    modules: defaultdict[str, defaultdict[str, dict[str, str]]] = defaultdict(lambda: defaultdict(dict))
    dist: defaultdict[str, defaultdict[str, dict[str, str]]] = defaultdict(lambda: defaultdict(dict))
    with zipfile.ZipFile(bio, "w") as zip_app:
        _write_packages_to_zipapp(base, dist, modules, packages, zip_app)
        zip_app.writestr(_entry("modules.json"), json.dumps(modules, indent=2))
        zip_app.writestr(_entry("distributions.json"), json.dumps(dist, indent=2))
        zip_app.writestr(_entry("__main__.py"), (_HERE / "__main__zipapp.py").read_bytes())
    bio.seek(0)
    zipapp.create_archive(bio, dest)
    # the build reports the archive it wrote to the terminal
    print(f"zipapp created at {dest} with size {os.path.getsize(dest) / 1024 / 1024:.2f}MB")  # ruff:ignore[print]


# the package walk keeps its branches together, one pass over the wheel contents
def _write_packages_to_zipapp(  # ruff:ignore[complex-structure, too-many-branches]
    base: PurePosixPath,
    dist: defaultdict[str, defaultdict[str, dict[str, str]]],
    modules: defaultdict[str, defaultdict[str, dict[str, str]]],
    packages: dict[str, dict[str, dict[str, WheelForVersion]]],
    zip_app: zipfile.ZipFile,
) -> None:
    has = set()
    # the nested loops walk each package and its files in one pass
    for name, p_w_v in packages.items():  # ruff:ignore[too-many-nested-blocks]
        for platform, w_v in p_w_v.items():
            for wheel_data in w_v.values():
                wheel = wheel_data.wheel
                with zipfile.ZipFile(str(wheel)) as wheel_zip:
                    for filename in wheel_zip.namelist():
                        if name == "virtualenv":
                            dest = PurePosixPath(filename)
                        else:
                            dest = base / wheel.stem / filename
                            if dest.suffix in {".so", ".pyi"}:
                                continue
                            if dest.suffix == ".py":
                                key = filename[:-3].replace("/", ".").replace("__init__", "").rstrip(".")
                                for version in wheel_data.versions:
                                    modules[version][platform][key] = str(dest)
                            if dest.parent.suffix == ".dist-info":
                                dist_name = dest.parent.stem.split("-")[0].replace("_", "-")
                                for version in wheel_data.versions:
                                    dist[version][platform][dist_name] = str(dest.parent)
                        dest_str = str(dest)
                        if dest_str in has:
                            continue
                        has.add(dest_str)
                        if "/tests/" in dest_str or "/docs/" in dest_str:
                            continue
                        # the build lists each file it adds, for the developer at the terminal
                        print(dest_str)  # ruff:ignore[print]
                        content = wheel_zip.read(filename)
                        zip_app.writestr(_entry(dest_str), content)
                        del content


def _entry(name: str) -> zipfile.ZipInfo:
    # the build time and OS would otherwise end up in each entry header; 1580601600 is hatchling's fallback, so the
    # entries share the timestamp of the SBOM appended after them
    epoch: Final[int] = int(os.environ.get("SOURCE_DATE_EPOCH", "1580601600"))
    entry: Final[zipfile.ZipInfo] = zipfile.ZipInfo(
        name, datetime.fromtimestamp(epoch, tz=timezone.utc).timetuple()[:6]
    )
    entry.create_system = 3
    entry.external_attr = 0o644 << 16
    return entry


if __name__ == "__main__":
    main()


__all__ = [
    "python_versions_for",
]
