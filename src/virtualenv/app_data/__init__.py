"""Application data stored by virtualenv."""

from __future__ import annotations

import logging
import os
import shutil
from typing import TYPE_CHECKING, Final

from platformdirs import user_cache_dir, user_data_dir

from .na import AppDataDisabled
from .read_only import ReadOnlyAppData
from .via_disk_folder import AppDataDiskFolder
from .via_tempdir import TempAppData

if TYPE_CHECKING:
    from collections.abc import Mapping

    from .base import AppData

_LOGGER: Final = logging.getLogger(__name__)


def make_app_data(folder: str | None, *, read_only: bool, env: Mapping[str, str]) -> AppData:
    private: Final = folder is None and "VIRTUALENV_OVERRIDE_APP_DATA" not in env
    if folder is None:
        folder = _default_app_data_dir(env)
    folder = os.path.abspath(folder)

    if read_only:
        return ReadOnlyAppData(folder)

    try:
        os.makedirs(folder, mode=0o700 if private else 0o777, exist_ok=True)
        if private and os.name == "posix":
            os.chmod(folder, 0o700)
        _LOGGER.debug("created app data folder %s", folder)
    except OSError as exception:
        _LOGGER.info("could not prepare app data folder %s due to %r", folder, exception)
        if private:
            return TempAppData()

    if os.access(folder, os.W_OK):
        return AppDataDiskFolder(folder)
    _LOGGER.debug("app data folder %s has no write access", folder)
    return TempAppData()


def _default_app_data_dir(env: Mapping[str, str]) -> str:
    key: Final = "VIRTUALENV_OVERRIDE_APP_DATA"
    if key in env:
        return env[key]
    return _cache_dir_with_migration()


def _cache_dir_with_migration() -> str:
    new_dir: Final = user_cache_dir(appname="virtualenv", appauthor="pypa")
    old_dir: Final = user_data_dir(appname="virtualenv", appauthor="pypa")
    if new_dir == old_dir:
        return new_dir
    if os.path.isdir(old_dir) and not os.path.isdir(new_dir):
        _LOGGER.info("migrating app data from %s to %s", old_dir, new_dir)
        try:
            shutil.move(old_dir, new_dir)
        except OSError as exception:
            _LOGGER.warning(
                "could not migrate app data from %s to %s: %r, using old location", old_dir, new_dir, exception
            )
            return old_dir
    return new_dir


__all__ = (
    "AppDataDisabled",
    "AppDataDiskFolder",
    "ReadOnlyAppData",
    "TempAppData",
    "make_app_data",
)
