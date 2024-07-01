"""Helper script to rebuild virtualenv_support. Downloads the wheel files using pip."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from collections import OrderedDict, defaultdict
from pathlib import Path
from tempfile import TemporaryDirectory
from textwrap import dedent
from threading import Thread

STRICT = "UPGRADE_ADVISORY" not in os.environ

BUNDLED = ["pip", "setuptools", "wheel"]
SUPPORT = [(3, i) for i in range(7, 15)]
DEST = Path(__file__).resolve().parents[1] / "src" / "virtualenv" / "seed" / "wheels" / "embed"


def download(ver, dest, package):
    subprocess.call(
        [
            sys.executable,
            "-m",
            "pip",
            "--disable-pip-version-check",
            "download",
            "--only-binary=:all:",
            "--python-version",
            ver,
            "-d",
            dest,
            package,
        ],
    )


def run():  # noqa: C901
    old_batch = {i.name for i in DEST.iterdir() if i.suffix == ".whl"}
    with TemporaryDirectory() as temp:
        temp_path = Path(temp)
        folders = {}
        targets = []
        for support in SUPPORT:
            support_ver = ".".join(str(i) for i in support)
            into = temp_path / support_ver
            into.mkdir()
            folders[into] = support_ver
            for package in BUNDLED:
                thread = Thread(target=download, args=(support_ver, str(into), package))
                targets.append(thread)
                thread.start()
        for thread in targets:
            thread.join()
        new_batch = {i.name: i for f in folders for i in Path(f).iterdir()}

        new_packages = new_batch.keys() - old_batch
        remove_packages = old_batch - new_batch.keys()

        for package in remove_packages:
            (DEST / package).unlink()
        for package in new_packages:
            shutil.copy2(str(new_batch[package]), DEST / package)

        added = collect_package_versions(new_packages)
        removed = collect_package_versions(remove_packages)

        outcome = (1 if STRICT else 0) if (added or removed) else 0
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
        support_table = OrderedDict((".".join(str(j) for j in i), []) for i in SUPPORT)
        for package in sorted(new_batch.keys()):
            for folder, version in sorted(folders.items()):
                if (folder / package).exists():
                    support_table[version].append(package)
        support_table = {k: OrderedDict((i.split("-")[0], i) for i in v) for k, v in support_table.items()}
        bundle = ",".join(
            f"{v!r}: {{ {','.join(f'{p!r}: {f!r}' for p, f in line.items())} }}" for v, line in support_table.items()
        )
        msg = dedent(
            f"""
        from pathlib import Path

        from virtualenv.seed.wheels.util import Wheel

        BUNDLE_FOLDER = Path(__file__).absolute().parent
        BUNDLE_SUPPORT = {{ {bundle} }}
        MAX = {next(iter(support_table.keys()))!r}


        def get_embed_wheel(distribution, for_py_version):
            path = BUNDLE_FOLDER / (BUNDLE_SUPPORT.get(for_py_version, {{}}) or BUNDLE_SUPPORT[MAX]).get(distribution)
            return Wheel.from_path(path)


        __all__ = [
            "get_embed_wheel",
            "BUNDLE_SUPPORT",
            "MAX",
            "BUNDLE_FOLDER",
        ]

        """,
        )
        dest_target = DEST / "__init__.py"
        dest_target.write_text(msg, encoding="utf-8")

        subprocess.run(
            [sys.executable, "-m", "ruff", "check", str(dest_target), "--fix", "--unsafe-fixes"],
            check=False,
        )
        subprocess.run(
            [sys.executable, "-m", "ruff", "format", str(dest_target), "--preview"],
            check=False,
        )

        raise SystemExit(outcome)


def fmt_version(versions):
    return ", ".join(f"``{v}``" for v in versions)


def collect_package_versions(new_packages):
    result = defaultdict(list)
    for package in new_packages:
        split = package.split("-")
        if len(split) < 2:  # noqa: PLR2004
            raise ValueError(package)
        key, version = split[0:2]
        result[key].append(version)
    return result


if __name__ == "__main__":
    run()
