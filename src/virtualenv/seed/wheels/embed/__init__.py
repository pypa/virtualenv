from __future__ import annotations

from virtualenv.info import IS_ZIPAPP as IS_ZIPAPP
from virtualenv.info import ROOT as ROOT
from virtualenv.seed.wheels.util import Wheel as Wheel

from .catalog import (
    BUNDLE_FOLDER,
    BUNDLE_SHA256,
    BUNDLE_SUPPORT,
    MAX,
    MIN,
    OLDEST_SUPPORTED,
    get_embed_wheel,
)

__all__ = [
    "BUNDLE_FOLDER",
    "BUNDLE_SHA256",
    "BUNDLE_SUPPORT",
    "MAX",
    "MIN",
    "OLDEST_SUPPORTED",
    "get_embed_wheel",
]
