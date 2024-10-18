"""https://docs.python.org/3/library/zipapp.html."""

from __future__ import annotations

import argparse
import io
import json
import os
import shutil
import subprocess
import sys
import zipapp
import zipfile
from collections import defaultdict, deque
from email import message_from_string
from pathlib import Path, PurePosixPath
from shlex import quote
from stat import S_IWUSR
from tempfile import TemporaryDirectory

from packaging.markers import Marker
from packaging.requirements import Requirement

HERE = Path(__file__).parent.absolute()

VERSIONS = [f"3.{i}" for i in range(13, 7, -1)]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dest", default="virtualenv.pyz")
    args = parser.parse_args()
    with TemporaryDirectory() as folder:
        packages = get_wheels_for_support_versions(Path(folder))
        create_zipapp(os.path.abspath(args.dest), packages)


def create_zipapp(dest, packages):
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
    print(f"zipapp created at {dest} with size {os.path.getsize(dest) / 1024 / 1024:.2f}MB")  # noqa: T201


def write_packages_to_zipapp(base, dist, modules, packages, zip_app):  # noqa: C901, PLR0912
    has = set()
    for name, p_w_v in packages.items():  # noqa: PLR1702
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
                                for version in wheel_data.versions:
                                    dist[version][platform][dest.parent.stem.split("-")[0]] = str(dest.parent)
                        dest_str = str(dest)
                        if dest_str in has:
                            continue
                        has.add(dest_str)
                        if "/tests/" in dest_str or "/docs/" in dest_str:
                            continue
                        print(dest_str)  # noqa: T201
                        content = wheel_zip.read(filename)
                        zip_app.writestr(dest_str, content)
                        del content


class WheelDownloader:
    def __init__(self, into) -> None:
        if into.exists():
            shutil.rmtree(into)
        into.mkdir(parents=True)
        self.into = into
        self.collected = defaultdict(lambda: defaultdict(dict))
        self.pip_cmd = [str(Path(sys.executable).parent / "pip")]
        self._cmd = [*self.pip_cmd, "download", "-q", "--no-deps", "--dest", str(self.into)]

    def run(self, target, versions):
        whl = self.build_sdist(target)
        todo = deque((version, None, whl) for version in versions)
        wheel_store = {}
        while todo:
            version, platform, dep = todo.popleft()
            dep_str = dep.name.split("-")[0] if isinstance(dep, Path) else dep.name
            if dep_str in self.collected[version] and platform in self.collected[version][dep_str]:
                continue
            whl = self._get_wheel(dep, platform[2:] if platform and platform.startswith("==") else None, version)
            if whl is None:
                if dep_str not in wheel_store:
                    msg = f"failed to get {dep_str}, have {wheel_store}"
                    raise RuntimeError(msg)
                whl = wheel_store[dep_str]
            else:
                wheel_store[dep_str] = whl
            self.collected[version][dep_str][platform] = whl
            todo.extend(self.get_dependencies(whl, version))

    def _get_wheel(self, dep, platform, version):
        if isinstance(dep, Requirement):
            before = set(self.into.iterdir())
            if self._download(
                platform,
                False,  # noqa: FBT003
                "--python-version",
                version,
                "--only-binary",
                ":all:",
                str(dep),
            ):
                self._download(platform, True, "--python-version", version, str(dep))  # noqa: FBT003
            after = set(self.into.iterdir())
            new_files = after - before
            assert len(new_files) <= 1  # noqa: S101
            if not len(new_files):
                return None
            new_file = next(iter(new_files))
            if new_file.suffix == ".whl":
                return new_file
            dep = new_file
        new_file = self.build_sdist(dep)
        assert new_file.suffix == ".whl"  # noqa: S101
        return new_file

    def _download(self, platform, stop_print_on_fail, *args):
        exe_cmd = self._cmd + list(args)
        if platform is not None:
            exe_cmd.extend(["--platform", platform])
        return run_suppress_output(exe_cmd, stop_print_on_fail=stop_print_on_fail)

    @staticmethod
    def get_dependencies(whl, version):
        with zipfile.ZipFile(str(whl), "r") as zip_file:
            name = "/".join([f"{'-'.join(whl.name.split('-')[0:2])}.dist-info", "METADATA"])
            with zip_file.open(name) as file_handler:
                metadata = message_from_string(file_handler.read().decode("utf-8"))
        deps = metadata.get_all("Requires-Dist")
        if deps is None:
            return
        for dep in deps:
            req = Requirement(dep)
            markers = getattr(req.marker, "_markers", ()) or ()
            if any(
                m
                for m in markers
                if isinstance(m, tuple) and len(m) == 3 and m[0].value == "extra"  # noqa: PLR2004
            ):
                continue
            py_versions = WheelDownloader._marker_at(markers, "python_version")
            if py_versions:
                marker = Marker('python_version < "1"')
                marker._markers = [  # noqa: SLF001
                    markers[ver] for ver in sorted(i for i in set(py_versions) | {i - 1 for i in py_versions} if i >= 0)
                ]
                matches_python = marker.evaluate({"python_version": version})
                if not matches_python:
                    continue
                deleted = 0
                for ver in py_versions:
                    deleted += WheelDownloader._del_marker_at(markers, ver - deleted)
            platforms = []
            platform_positions = WheelDownloader._marker_at(markers, "sys_platform")
            deleted = 0
            for pos in platform_positions:  # can only be or meaningfully
                platform = f"{markers[pos][1].value}{markers[pos][2].value}"
                deleted += WheelDownloader._del_marker_at(markers, pos - deleted)
                platforms.append(platform)
            if not platforms:
                platforms.append(None)
            for platform in platforms:
                yield version, platform, req

    @staticmethod
    def _marker_at(markers, key):
        return [
            i
            for i, m in enumerate(markers)
            if isinstance(m, tuple) and len(m) == 3 and m[0].value == key  # noqa: PLR2004
        ]

    @staticmethod
    def _del_marker_at(markers, at):
        del markers[at]
        deleted = 1
        op = max(at - 1, 0)
        if markers and isinstance(markers[op], str):
            del markers[op]
            deleted += 1
        return deleted

    def build_sdist(self, target):
        if target.is_dir():
            # pip 20.1 no longer guarantees this to be parallel safe, need to copy/lock
            with TemporaryDirectory() as temp_folder:
                folder = Path(temp_folder) / target.name
                shutil.copytree(
                    str(target),
                    str(folder),
                    ignore=shutil.ignore_patterns(".tox", ".tox4", "venv", "__pycache__", "*.pyz"),
                )
                try:
                    return self._build_sdist(self.into, folder)
                finally:
                    # permission error on Windows <3.7 https://bugs.python.org/issue26660
                    def onerror(func, path, exc_info):  # noqa: ARG001
                        os.chmod(path, S_IWUSR)
                        func(path)

                    shutil.rmtree(str(folder), onerror=onerror)

        else:
            return self._build_sdist(target.parent / target.stem, target)

    def _build_sdist(self, folder, target):
        if not folder.exists() or not list(folder.iterdir()):
            cmd = [*self.pip_cmd, "wheel", "-w", str(folder), "--no-deps", str(target), "-q"]
            run_suppress_output(cmd, stop_print_on_fail=True)
        return next(iter(folder.iterdir()))


def run_suppress_output(cmd, stop_print_on_fail=False):  # noqa: FBT002
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        encoding="utf-8",
    )
    out, err = process.communicate()
    if stop_print_on_fail and process.returncode != 0:
        print(f"exit with {process.returncode} of {' '.join(quote(i) for i in cmd)}", file=sys.stdout)  # noqa: T201
        if out:
            print(out, file=sys.stdout)  # noqa: T201
        if err:
            print(err, file=sys.stderr)  # noqa: T201
        raise SystemExit(process.returncode)
    return process.returncode


def get_wheels_for_support_versions(folder):
    downloader = WheelDownloader(folder / "wheel-store")
    downloader.run(HERE.parent, VERSIONS)
    packages = defaultdict(lambda: defaultdict(lambda: defaultdict(WheelForVersion)))
    for version, collected in downloader.collected.items():
        for pkg, platform_to_wheel in collected.items():
            name = Requirement(pkg).name
            for platform, wheel in platform_to_wheel.items():
                pl = platform or "==any"
                wheel_versions = packages[name][pl][wheel.name]
                wheel_versions.versions.append(version)
                wheel_versions.wheel = wheel
    for name, p_w_v in packages.items():
        for platform, w_v in p_w_v.items():
            print(f"{name} - {platform}")  # noqa: T201
            for wheel, wheel_versions in w_v.items():
                print(f"{' '.join(wheel_versions.versions)} of {wheel} (use {wheel_versions.wheel})")  # noqa: T201
    return packages


class WheelForVersion:
    def __init__(self, wheel=None, versions=None) -> None:
        self.wheel = wheel
        self.versions = versions or []

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.wheel!r}, {self.versions!r})"


if __name__ == "__main__":
    main()
