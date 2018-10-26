"""
Helper script to rebuild virtualenv_support. Downloads the wheel files using pip
"""

import glob
import os
import subprocess


def virtualenv_support_path():
    return os.path.join(os.path.dirname(__file__), "../src/virtualenv_support")


def remove_wheel_files():
    for file in glob.glob(virtualenv_support_path() + "/*.whl"):
        os.remove(file)


def download(package):
    subprocess.call(["pip", "download", "-d", virtualenv_support_path(), package])


if __name__ == "__main__":
    remove_wheel_files()
    download("pip")
    download("wheel")
    download("setuptools")
