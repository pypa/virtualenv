from __future__ import annotations

import sys

from setuptools import Extension, setup

setup(
    name="greet",  # package name
    version="1.0",  # package version
    ext_modules=[
        Extension(
            "greet",
            [f"greet{sys.version_info[0]}.c"],  # extension to package
        ),  # C code to compile to run as extension
    ],
)
