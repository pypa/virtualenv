from __future__ import absolute_import, unicode_literals

from virtualenv.seed.wheels.util import Wheel
from virtualenv.util.path import Path

BUNDLE_FOLDER = Path(__file__).absolute().parent
BUNDLE_SUPPORT = {
    "3.10": {
        "pip": "pip-20.2.3-py2.py3-none-any.whl",
        "setuptools": "setuptools-50.3.0-py3-none-any.whl",
        "wheel": "wheel-0.35.1-py2.py3-none-any.whl",
    },
    "3.9": {
        "pip": "pip-20.2.3-py2.py3-none-any.whl",
        "setuptools": "setuptools-50.3.0-py3-none-any.whl",
        "wheel": "wheel-0.35.1-py2.py3-none-any.whl",
    },
    "3.8": {
        "pip": "pip-20.2.3-py2.py3-none-any.whl",
        "setuptools": "setuptools-50.3.0-py3-none-any.whl",
        "wheel": "wheel-0.35.1-py2.py3-none-any.whl",
    },
    "3.7": {
        "pip": "pip-20.2.3-py2.py3-none-any.whl",
        "setuptools": "setuptools-50.3.0-py3-none-any.whl",
        "wheel": "wheel-0.35.1-py2.py3-none-any.whl",
    },
    "3.6": {
        "pip": "pip-20.2.3-py2.py3-none-any.whl",
        "setuptools": "setuptools-50.3.0-py3-none-any.whl",
        "wheel": "wheel-0.35.1-py2.py3-none-any.whl",
    },
    "3.5": {
        "pip": "pip-20.2.3-py2.py3-none-any.whl",
        "setuptools": "setuptools-50.3.0-py3-none-any.whl",
        "wheel": "wheel-0.35.1-py2.py3-none-any.whl",
    },
    "3.4": {
        "pip": "pip-19.1.1-py2.py3-none-any.whl",
        "setuptools": "setuptools-43.0.0-py2.py3-none-any.whl",
        "wheel": "wheel-0.33.6-py2.py3-none-any.whl",
    },
    "2.7": {
        "pip": "pip-20.2.3-py2.py3-none-any.whl",
        "setuptools": "setuptools-44.1.1-py2.py3-none-any.whl",
        "wheel": "wheel-0.35.1-py2.py3-none-any.whl",
    },
}
MAX = "3.10"
VERSION_DEPS = {
    "3.10": {"pip": [], "setuptools": [], "wheel": []},
    "3.9": {"pip": [], "setuptools": [], "wheel": []},
    "3.8": {"pip": [], "setuptools": [], "wheel": []},
    "3.7": {"pip": [], "setuptools": [], "wheel": []},
    "3.6": {"pip": [], "setuptools": [], "wheel": []},
    "3.5": {"pip": [], "setuptools": [], "wheel": []},
    "3.4": {"pip": [], "setuptools": [], "wheel": []},
    "2.7": {"pip": [], "setuptools": [], "wheel": []},
}


def get_embed_wheel(distribution, for_py_version):
    path = BUNDLE_FOLDER / (BUNDLE_SUPPORT.get(for_py_version, {}) or BUNDLE_SUPPORT[MAX]).get(distribution)
    return Wheel.from_path(path)


__all__ = (
    "get_embed_wheel",
    "BUNDLE_SUPPORT",
    "VERSION_DEPS",
    "MAX",
    "BUNDLE_FOLDER",
)
