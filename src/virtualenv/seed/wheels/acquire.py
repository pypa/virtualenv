"""Bootstrap"""
from __future__ import absolute_import, unicode_literals

from collections import defaultdict
from shutil import copy2

from pathlib2 import Path

from . import BUNDLE_SUPPORT, MAX

BUNDLE_FOLDER = Path(__file__).parent


def get_wheel(creator, cache):
    interpreter = creator.interpreter

    version_release = interpreter.version_release_str
    wheel_download = cache / "download" / version_release
    wheel_download.mkdir(parents=True, exist_ok=True)

    options = creator.options
    packages = {"pip": options.pip, "setuptools": options.setuptools}

    ensure_bundle_cached(
        packages, version_release, wheel_download
    )  # first ensure all bundled versions area already there
    if options.download is True:
        must_download = check_if_must_download(packages, wheel_download)  # check what needs downloading
        if must_download:  # perform download if any of the packages require
            download_wheel(version_release, must_download, wheel_download)
    return _get_wheels_for_package(wheel_download, packages)


def download_wheel(version_str, must_download, wheel_download):
    cmd = [
        "download",
        "--disable-pip-version-check",
        "--only-binary=:all:",
        "--no-deps",
        "--python-version",
        version_str,
        "-d",
        str(wheel_download),
    ]
    cmd.extend(must_download)
    from pip._internal import main

    main(cmd)


def check_if_must_download(packages, wheel_download):
    must_download = set()
    if any(i is not None for i in packages.values()):
        has_version = _get_wheels(wheel_download)
        for pkg, version in packages.items():
            if pkg in has_version and version in has_version[pkg]:
                continue
            must_download.add(pkg)
    return must_download


def _get_wheels(inside_folder):
    has_version = defaultdict(set)
    for filename in inside_folder.iterdir():
        if filename.suffix == ".whl":
            pkg, version = filename.stem.split("-")[0:2]
            has_version[pkg].add(version)
    return has_version


def _get_wheels_for_package(inside_folder, package):
    has_version = defaultdict(dict)
    for filename in inside_folder.iterdir():
        if filename.suffix == ".whl":
            pkg, version = filename.stem.split("-")[0:2]
            has_version[pkg][version] = filename
    result = {}
    for pkg, version in package.items():
        content = has_version[pkg]
        if version in content:
            result[pkg] = content[version]
        else:
            elements = sorted(
                content.items(),
                key=lambda a: tuple(int(i) if i.isdigit() else i for i in a[0].split(".")),
                reverse=True,
            )
            result[pkg] = elements[0][1]
    return result


def ensure_bundle_cached(packages, version_release, wheel_download):
    for package in packages:
        bundle = (BUNDLE_SUPPORT.get(version_release, {}) or BUNDLE_SUPPORT[MAX]).get(package)
        if bundle is not None:
            bundled_wheel_file = wheel_download / bundle
            if not bundled_wheel_file.exists():
                copy2(str(BUNDLE_FOLDER / bundle), str(bundled_wheel_file))
