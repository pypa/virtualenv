import sys

from setuptools import Extension, setup

setup(
    name="greet",  # package name
    version="1.0",  # package version
    ext_modules=[
        Extension(
            "greet",
            ["greet{}.c".format(sys.version_info[0])],  # extension to package
        ),  # C code to compile to run as extension
    ],
)
