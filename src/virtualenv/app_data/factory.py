from __future__ import annotations

import logging
import os
from argparse import ArgumentTypeError
from stat import S_IMODE, S_ISGID, S_IWGRP, S_IWOTH
from typing import TYPE_CHECKING, Final

from .cache_migration import _cache_dir_with_migration
from .read_only import ReadOnlyAppData
from .via_disk_folder import AppDataDiskFolder
from .via_tempdir import TempAppData

if TYPE_CHECKING:
    from collections.abc import Mapping

    from .base import AppData

_LOGGER: Final[logging.Logger] = logging.getLogger(__name__)


def make_app_data(folder: str | None, *, read_only: bool, env: Mapping[str, str]) -> AppData:
    private: Final = folder is None and not env.get("VIRTUALENV_OVERRIDE_APP_DATA", "").strip()
    if folder is None:
        folder = _default_app_data_dir(env)
    elif not folder.strip():
        # an empty value, often an unset shell variable, resolves to the working directory (on Windows so do spaces)
        # and --reset-app-data would delete it
        msg: Final[str] = f"app data folder {folder!r} must not be empty or whitespace"
        raise ArgumentTypeError(msg)
    folder = os.path.abspath(folder)

    if read_only:
        return ReadOnlyAppData(folder)

    try:
        os.makedirs(folder, mode=0o700 if private else 0o777, exist_ok=True)
        if private and os.name == "posix" and not _prepare_permissions(folder):
            return TempAppData()
        _LOGGER.debug("created app data folder %s", folder)
    except OSError as exception:
        _LOGGER.info("could not prepare app data folder %s due to %r", folder, exception)

    if os.access(folder, os.W_OK):
        return AppDataDiskFolder(folder)
    _LOGGER.debug("app data folder %s has no write access", folder)
    return TempAppData()


def _default_app_data_dir(env: Mapping[str, str]) -> str:
    # a blank value counts as unset, as an empty one does for the VIRTUALENV_<OPTION> variables; abspath would turn it
    # into the working directory (on Windows spaces too), which --reset-app-data then deletes
    if (folder := env.get("VIRTUALENV_OVERRIDE_APP_DATA", "")).strip():
        return folder
    return _cache_dir_with_migration()


def _prepare_permissions(folder: str) -> bool:
    info: Final = os.stat(folder)
    if info.st_uid != os.geteuid():
        _LOGGER.debug("app data folder %s is owned by uid %d, leaving its mode", folder, info.st_uid)
        return True
    # setgid marks a deliberately group-shared cache, so only other-write is dropped there
    loose: Final = info.st_mode & (S_IWOTH if info.st_mode & S_ISGID else S_IWGRP | S_IWOTH)
    if loose:
        try:
            os.chmod(folder, S_IMODE(info.st_mode) & ~loose)
        except OSError:
            _LOGGER.warning("using temporary app-data because default cache permissions could not be set")
            return False
    return True


__all__ = [
    "make_app_data",
]
