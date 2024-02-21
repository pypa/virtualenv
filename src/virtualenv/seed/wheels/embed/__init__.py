from __future__ import annotations

from pathlib import Path

from virtualenv.seed.wheels.util import Wheel

BUNDLE_FOLDER = Path(__file__).absolute().parent
BUNDLE_SUPPORT = {
    "3.7": {
        "pip": "pip-24.0-py3-none-any.whl",
        "setuptools": "setuptools-68.0.0-py3-none-any.whl",
        "wheel": "wheel-0.42.0-py3-none-any.whl",
    },
    "3.8": {
        "pip": "pip-24.0-py3-none-any.whl",
        "setuptools": "setuptools-69.1.0-py3-none-any.whl",
        "wheel": "wheel-0.42.0-py3-none-any.whl",
    },
    "3.9": {
        "pip": "pip-24.0-py3-none-any.whl",
        "setuptools": "setuptools-69.1.0-py3-none-any.whl",
        "wheel": "wheel-0.42.0-py3-none-any.whl",
    },
    "3.10": {
        "pip": "pip-24.0-py3-none-any.whl",
        "setuptools": "setuptools-69.1.0-py3-none-any.whl",
        "wheel": "wheel-0.42.0-py3-none-any.whl",
    },
    "3.11": {
        "pip": "pip-24.0-py3-none-any.whl",
        "setuptools": "setuptools-69.1.0-py3-none-any.whl",
        "wheel": "wheel-0.42.0-py3-none-any.whl",
    },
    "3.12": {
        "pip": "pip-24.0-py3-none-any.whl",
        "setuptools": "setuptools-69.1.0-py3-none-any.whl",
        "wheel": "wheel-0.42.0-py3-none-any.whl",
    },
    "3.13": {
        "pip": "pip-24.0-py3-none-any.whl",
        "setuptools": "setuptools-69.1.0-py3-none-any.whl",
        "wheel": "wheel-0.42.0-py3-none-any.whl",
    },
}
MAX = "3.7"


def get_embed_wheel(distribution, for_py_version):
    path = BUNDLE_FOLDER / (BUNDLE_SUPPORT.get(for_py_version, {}) or BUNDLE_SUPPORT[MAX]).get(distribution)
    return Wheel.from_path(path)


__all__ = [
    "BUNDLE_FOLDER",
    "BUNDLE_SUPPORT",
    "MAX",
    "get_embed_wheel",
]
