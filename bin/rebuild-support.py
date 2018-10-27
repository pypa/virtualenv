"""
Helper script to rebuild virtualenv_support. Downloads the wheel files using pip
"""

import glob
import os
import subprocess


def virtualenv_support_path():
    return os.path.join(os.path.dirname(__file__), "../src/virtualenv_support")


def collect_wheels():
    for file in glob.glob(virtualenv_support_path() + "/*.whl"):
        name, version = os.path.basename(file).split("-")[:2]
        yield file, name, version


def remove_wheel_files():
    old_versions = {}
    for file, name, version in collect_wheels():
        old_versions[name] = version
        os.remove(file)
    return old_versions


def download(package):
    subprocess.call(["pip", "download", "-d", virtualenv_support_path(), package])


def run():
    old = remove_wheel_files()
    for package in ("pip", "wheel", "setuptools"):
        download(package)
    new = {name: version for _, name, version in collect_wheels()}

    changes = []
    for package, version in old.items():
        if new[package] != version:
            changes.append((package, version, new[package]))

    print("\n".join(" * upgrade {} from {} to {}".format(p, o, n) for p, o, n in changes))


if __name__ == "__main__":
    run()
