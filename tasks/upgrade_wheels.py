"""
Helper script to rebuild virtualenv_support. Downloads the wheel files using pip
"""
from __future__ import absolute_import, unicode_literals

import os
import shutil
import subprocess
import sys
from collections import defaultdict
from concurrent.futures import as_completed
from concurrent.futures.thread import ThreadPoolExecutor
from pathlib import Path
from tempfile import TemporaryDirectory
from textwrap import dedent
from typing import Dict

STRICT = "UPGRADE_ADVISORY" not in os.environ

BUNDLED = ["pip", "setuptools", "wheel"]
SUPPORT = list(reversed([(2, 7)] + [(3, i) for i in range(4, 11)]))
DEST = Path(__file__).resolve().parents[1] / "src" / "virtualenv" / "seed" / "wheels" / "embed"


def download(ver: str, into: Path):
    dest = into / ver
    dest.mkdir()
    cmd = [
        sys.executable,
        "-m",
        "pip",
        "--disable-pip-version-check",
        "download",
        "--only-binary=:all:",
        "--python-version",
        ver,
    ]
    subprocess.check_call(cmd + ["-d", str(dest), *BUNDLED])
    deps = {}
    for pkg in BUNDLED:
        to_folder = dest / pkg
        to_folder.mkdir()
        try:
            subprocess.check_call(cmd + ["-d", str(to_folder), pkg])
            found = sorted(list(wheel.name.split("-")[0] for wheel in to_folder.iterdir()))
            found.remove(pkg)
            deps[pkg] = found
        finally:
            shutil.rmtree(to_folder)
    return ver, dest, deps


def run():
    if sys.version_info < (3, 7):
        raise RuntimeError("requires python 3.7 or later")
    old_batch = {i.name for i in DEST.iterdir() if i.suffix == ".whl"}
    with TemporaryDirectory() as temp:
        temp = Path(temp)
        bundle_support: Dict[str, Dict[str, str]] = {}
        version_deps = {}
        new_batch = {}
        with ThreadPoolExecutor(max_workers=4) as executor:
            for future in as_completed({executor.submit(download, ".".join(str(i) for i in s), temp) for s in SUPPORT}):
                try:
                    version, dest, deps = future.result()
                except Exception as exc:
                    raise exc
                else:
                    bundle = {}
                    for wheel in dest.iterdir():
                        name = wheel.name.split("-")[0]
                        bundle[name] = wheel.name
                        new_batch[wheel.name] = wheel
                    wheels = {wheel.name.split("-")[0]: wheel.name for wheel in dest.iterdir()}
                    wheels = {k: v for k, v in sorted(wheels.items())}
                    bundle_support[version] = wheels
                    version_deps[version] = deps
        sort_by_version = lambda i: tuple(int(j) for j in i[0].split("."))  # noqa
        bundle_support = {k: v for k, v in sorted(bundle_support.items(), key=sort_by_version, reverse=True)}
        version_deps = {k: v for k, v in sorted(version_deps.items(), key=sort_by_version, reverse=True)}
        new_packages = new_batch.keys() - old_batch
        remove_packages = old_batch - new_batch.keys()

        for package in remove_packages:
            (DEST / package).unlink()
        for package in new_packages:
            shutil.copy2(str(new_batch[package]), DEST / package)

        added = collect_package_versions(new_packages)
        removed = collect_package_versions(remove_packages)

        outcome = (1 if STRICT else 0) if (added or removed) else 0
        for key, versions in added.items():
            text = "* upgrade embedded {} to {}".format(key, fmt_version(versions))
            if key in removed:
                text += " from {}".format(removed[key])
                del removed[key]
            print(text)
        for key, versions in removed.items():
            print("* removed embedded {} of {}".format(key, fmt_version(versions)))

        msg = dedent(
            """
        from __future__ import absolute_import, unicode_literals

        from virtualenv.seed.wheels.util import Wheel
        from virtualenv.util.path import Path

        BUNDLE_FOLDER = Path(__file__).absolute().parent
        BUNDLE_SUPPORT = {0}
        MAX = {1}
        VERSION_DEPS = {2}


        def get_embed_wheel(distribution, for_py_version):
            path = BUNDLE_FOLDER / (BUNDLE_SUPPORT.get(for_py_version, {{}}) or BUNDLE_SUPPORT[MAX]).get(distribution)
            return Wheel.from_path(path)


        __all__ = (
            "get_embed_wheel",
            "BUNDLE_SUPPORT",
            "VERSION_DEPS",
            "MAX",
            "BUNDLE_FOLDER",
        )

        """.format(
                repr(bundle_support), repr(next(iter(bundle_support.keys()))), repr(version_deps),
            ),
        )
        dest_target = DEST / "__init__.py"
        dest_target.write_text(msg)

        subprocess.run([sys.executable, "-m", "black", str(dest_target)])

        raise SystemExit(outcome)


def fmt_version(versions):
    return ", ".join("``{}``".format(v) for v in versions)


def collect_package_versions(new_packages):
    result = defaultdict(list)
    for package in new_packages:
        split = package.split("-")
        if len(split) < 2:
            raise ValueError(package)
        key, version = split[0:2]
        result[key].append(version)
    return result


if __name__ == "__main__":
    run()
