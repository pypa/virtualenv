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
from pathlib import Path, PurePosixPath
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING, Any, Final
from urllib.request import urlopen

from packaging.markers import Marker

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


HERE = Path(__file__).parent.absolute()

VERSIONS = [f"3.{i}" for i in range(14, 7, -1)]
LOCK: Final[Path] = HERE.parent / "pylock.zipapp.toml"
PLATFORMS: Final[tuple[str, ...]] = ("darwin", "linux", "win32")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dest", default="virtualenv.pyz")
    args = parser.parse_args()
    with TemporaryDirectory() as folder:
        packages = get_wheels_for_support_versions(Path(folder))
        create_zipapp(os.path.abspath(args.dest), packages)


def get_wheels_for_support_versions(folder: Path) -> dict[str, dict[str, dict[str, WheelForVersion]]]:
    packages: defaultdict[str, dict[str, dict[str, WheelForVersion]]] = defaultdict(lambda: {"==any": {}})
    wheel = build_virtualenv_wheel(folder)
    packages["virtualenv"]["==any"][wheel.name] = WheelForVersion(wheel, list(VERSIONS))
    for package in tomllib.loads(LOCK.read_text(encoding="utf-8"))["packages"]:
        wheel = download_locked_wheel(package, folder)
        packages[package["name"]]["==any"][wheel.name] = WheelForVersion(wheel, python_versions_for(package))
    for name, platforms in packages.items():
        for wheel_name, wheel_for_version in platforms["==any"].items():
            sys.stdout.write(f"{name}: {wheel_name} for {' '.join(wheel_for_version.versions)}\n")
    return packages


def build_virtualenv_wheel(into: Path) -> Path:
    with TemporaryDirectory() as temp_folder:
        # pip does not guarantee building from the same source tree in parallel is safe, so build from a copy
        source = Path(temp_folder) / HERE.parent.name
        shutil.copytree(
            HERE.parent, source, ignore=shutil.ignore_patterns(".tox", ".tox4", "venv", "__pycache__", "*.pyz")
        )
        subprocess.run(
            [sys.executable, "-m", "pip", "wheel", "-q", "--no-deps", "-w", str(into), str(source)], check=True
        )
    return next(into.glob("virtualenv-*.whl"))


def download_locked_wheel(package: LockedPackage, into: Path) -> Path:
    # the zipapp cannot load compiled extensions, so only a pure-Python wheel can be bundled
    if not (wheels := [wheel for wheel in package.get("wheels", []) if wheel["url"].endswith("-none-any.whl")]):
        msg = f"{LOCK.name} has no pure-Python wheel for {package['name']} {package['version']}"
        raise RuntimeError(msg)
    url, expected = wheels[0]["url"], wheels[0]["hashes"]["sha256"]
    with urlopen(url, timeout=60) as response:  # ruff:ignore[suspicious-url-open-usage]  # lock URL, sha256-checked
        content = response.read()
    if (actual := hashlib.sha256(content).hexdigest()) != expected:
        msg = f"{url} has sha256 {actual}, but {LOCK.name} records {expected}"
        raise RuntimeError(msg)
    (dest := into / url.rsplit("/", 1)[1]).write_bytes(content)
    return dest


def python_versions_for(package: LockedPackage) -> list[str]:
    if (marker := package.get("marker")) is None:
        return list(VERSIONS)
    parsed, versions = Marker(marker), []
    for version in VERSIONS:
        environment = {"python_version": version, "python_full_version": f"{version}.0"}
        # every bundled wheel is keyed as ==any, so a marker that differs per platform would ship the build host's pick
        if len(matches := {parsed.evaluate({**environment, "sys_platform": p}) for p in PLATFORMS}) != 1:
            msg = f"{LOCK.name} marks {package['name']} as platform specific ({marker}), which the zipapp cannot select"
            raise RuntimeError(msg)
        if matches.pop():
            versions.append(version)
    return versions


@dataclass(frozen=True)
class WheelForVersion:
    wheel: Path
    versions: list[str]


def create_zipapp(dest: str, packages: dict[str, dict[str, dict[str, WheelForVersion]]]) -> None:
    bio = io.BytesIO()
    base = PurePosixPath("__virtualenv__")
    modules = defaultdict(lambda: defaultdict(dict))
    dist = defaultdict(lambda: defaultdict(dict))
    with zipfile.ZipFile(bio, "w") as zip_app:
        write_packages_to_zipapp(base, dist, modules, packages, zip_app)
        modules_json = json.dumps(modules, indent=2)
        zip_app.writestr("modules.json", modules_json)
        distributions_json = json.dumps(dist, indent=2)
        zip_app.writestr("distributions.json", distributions_json)
        zip_app.writestr("__main__.py", (HERE / "__main__zipapp.py").read_bytes())
    bio.seek(0)
    zipapp.create_archive(bio, dest)
    print(f"zipapp created at {dest} with size {os.path.getsize(dest) / 1024 / 1024:.2f}MB")  # ruff:ignore[print]


def write_packages_to_zipapp(  # ruff:ignore[complex-structure, too-many-branches]
    base: PurePosixPath,
    dist: dict[str, Any],
    modules: dict[str, Any],
    packages: dict[str, dict[str, dict[str, WheelForVersion]]],
    zip_app: zipfile.ZipFile,
) -> None:
    has = set()
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
                        print(dest_str)  # ruff:ignore[print]
                        content = wheel_zip.read(filename)
                        zip_app.writestr(dest_str, content)
                        del content


if __name__ == "__main__":
    main()
