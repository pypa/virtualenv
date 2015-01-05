from __future__ import absolute_import, division, print_function

import os
import sys

import setuptools

if sys.version_info[:2] < (2, 6):
    sys.exit("virtualenv requires Python 2.6 or higher.")

base_dir = os.path.dirname(__file__)

# Fetch the metadata
about = {}
with open(os.path.join(base_dir, "virtualenv", "__about__.py")) as f:
    exec(f.read(), about)


# Build up the long description
with open(os.path.join(base_dir, "docs", "index.rst")) as f:
    long_description = f.read()
    long_description = long_description.strip().split("split here", 1)[0]

with open(os.path.join(base_dir, "docs", "changes.rst")) as f:
    long_description = "\n\n".join([long_description, f.read()])


setuptools.setup(
    name=about["__title__"],
    version=about["__version__"],

    description=about["__summary__"],
    long_description=long_description,
    license=about["__license__"],
    url=about["__uri__"],

    author=about["__author__"],
    author_email=about["__email__"],

    classifiers=[
        "Intended Audience :: Developers",

        "License :: OSI Approved :: MIT License",

        "Programming Language :: Python",
        "Programming Language :: Python :: 2",
        "Programming Language :: Python :: 2.6",
        "Programming Language :: Python :: 2.7",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.2",
        "Programming Language :: Python :: 3.3",
        "Programming Language :: Python :: 3.4",
    ],

    packages=[
        "virtualenv",
        "virtualenv.builders",
        "virtualenv.flavors",
        "virtualenv._scripts",
        "virtualenv._wheels",
    ],

    package_data={
        "virtualenv._scripts": ["activate.*", "deactivate.bat"],
        "virtualenv._wheels": ["*.whl"],
    },

    entry_points={
        "console_scripts": [
            "virtualenv=virtualenv.__main__:main",
        ],
    },

    install_requires=[
        "click",
    ],

    zip_safe=False,
)
