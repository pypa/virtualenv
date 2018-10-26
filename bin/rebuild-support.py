#!/usr/bin/env python

"""
Helper script to rebuild virtualenv_support. Downloads the wheel files using pip
"""

import glob
import os
import subprocess

def removeWheelFiles():
    for file in glob.glob("../src/virtualenv_support/*.whl"):
        os.remove(file)

def download(package):
    subprocess.call(["pip", "download", "-d", "../src/virtualenv_support", package])

if __name__ == '__main__':
    removeWheelFiles()
    download("pip")
    download("wheel")
    download("setuptools")
