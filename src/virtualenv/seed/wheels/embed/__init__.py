from __future__ import annotations

import hashlib
import zipfile
from pathlib import Path

from virtualenv.info import IS_ZIPAPP, ROOT
from virtualenv.seed.wheels.util import Wheel

BUNDLE_FOLDER = Path(__file__).absolute().parent
BUNDLE_SUPPORT = {
    "3.8": {
        "pip": "pip-25.0.1-py3-none-any.whl",
        "setuptools": "setuptools-75.3.4-py3-none-any.whl",
        "wheel": "wheel-0.45.1-py3-none-any.whl",
    },
    "3.9": {
        "pip": "pip-26.0.1-py3-none-any.whl",
        "setuptools": "setuptools-82.0.1-py3-none-any.whl",
    },
    "3.10": {
        "pip": "pip-26.1.1-py3-none-any.whl",
        "setuptools": "setuptools-82.0.1-py3-none-any.whl",
    },
    "3.11": {
        "pip": "pip-26.1.1-py3-none-any.whl",
        "setuptools": "setuptools-82.0.1-py3-none-any.whl",
    },
    "3.12": {
        "pip": "pip-26.1.1-py3-none-any.whl",
        "setuptools": "setuptools-82.0.1-py3-none-any.whl",
    },
    "3.13": {
        "pip": "pip-26.1.1-py3-none-any.whl",
        "setuptools": "setuptools-82.0.1-py3-none-any.whl",
    },
    "3.14": {
        "pip": "pip-26.1.1-py3-none-any.whl",
        "setuptools": "setuptools-82.0.1-py3-none-any.whl",
    },
    "3.15": {
        "pip": "pip-26.1.1-py3-none-any.whl",
        "setuptools": "setuptools-82.0.1-py3-none-any.whl",
    },
    "3.16": {
        "pip": "pip-26.1.1-py3-none-any.whl",
        "setuptools": "setuptools-82.0.1-py3-none-any.whl",
    },
}
MAX = next(reversed(BUNDLE_SUPPORT))

# SHA-256 of every bundled wheel. Verified on load so a corrupted or tampered wheel on disk fails loud instead of
# being handed to pip. Generated together with ``BUNDLE_SUPPORT`` by ``tasks/upgrade_wheels.py``.
BUNDLE_SHA256 = {
    "pip-25.0.1-py3-none-any.whl": "c46efd13b6aa8279f33f2864459c8ce587ea6a1a59ee20de055868d8f7688f7f",
    "pip-26.0.1-py3-none-any.whl": "bdb1b08f4274833d62c1aa29e20907365a2ceb950410df15fc9521bad440122b",
    "pip-26.1.1-py3-none-any.whl": "99cb1c2899893b075ff56e4ed0af55669a955b49ad7fb8d8603ecdaf4ed653fb",
    "setuptools-75.3.4-py3-none-any.whl": "2dd50a7f42dddfa1d02a36f275dbe716f38ed250224f609d35fb60a09593d93e",
    "setuptools-82.0.1-py3-none-any.whl": "a59e362652f08dcd477c78bb6e7bd9d80a7995bc73ce773050228a348ce2e5bb",
    "wheel-0.45.1-py3-none-any.whl": "708e7481cc80179af0e556bbf0cc00b8444c7321e2700b8d8580231d13017248",
}

_VERIFIED_WHEELS: set[str] = set()


def get_embed_wheel(distribution: str, for_py_version: str) -> Wheel | None:
    """Return the bundled wheel that ships with virtualenv for a given distribution and Python version.

    :param distribution: project name of the seed package, for example ``pip`` or ``setuptools``.
    :param for_py_version: major.minor Python version string the environment will be created for.

    :returns: a :class:`Wheel` pointing at the verified bundled file, or ``None`` when no wheel is bundled for the
        requested combination.

    :raises RuntimeError: if the bundled wheel on disk fails SHA-256 verification.

    """
    mapping = BUNDLE_SUPPORT.get(for_py_version, {}) or BUNDLE_SUPPORT[MAX]
    wheel_file = mapping.get(distribution)
    if wheel_file is None:
        return None
    path = BUNDLE_FOLDER / wheel_file
    _verify_bundled_wheel(path)
    return Wheel.from_path(path)


def _verify_bundled_wheel(path: Path) -> None:
    name = path.name
    if name in _VERIFIED_WHEELS:
        return
    expected = BUNDLE_SHA256.get(name)
    if expected is None:
        msg = f"bundled wheel {name} has no recorded sha256 in BUNDLE_SHA256"
        raise RuntimeError(msg)
    actual = _hash_bundled_wheel(path)
    if actual != expected:
        msg = f"bundled wheel {name} sha256 mismatch: expected {expected}, got {actual}"
        raise RuntimeError(msg)
    _VERIFIED_WHEELS.add(name)


def _hash_bundled_wheel(path: Path) -> str:
    # ``path`` is under the package directory; when virtualenv runs from a zipapp the wheel lives inside the
    # archive and cannot be opened as a regular file, so read the bytes straight from the zipapp entry.
    digest = hashlib.sha256()
    if IS_ZIPAPP:
        entry = path.resolve().relative_to(Path(ROOT).resolve()).as_posix()
        with zipfile.ZipFile(ROOT, "r") as archive, archive.open(entry) as stream:
            for chunk in iter(lambda: stream.read(1 << 20), b""):
                digest.update(chunk)
    else:
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1 << 20), b""):
                digest.update(chunk)
    return digest.hexdigest()


__all__ = [
    "BUNDLE_FOLDER",
    "BUNDLE_SHA256",
    "BUNDLE_SUPPORT",
    "MAX",
    "get_embed_wheel",
]
