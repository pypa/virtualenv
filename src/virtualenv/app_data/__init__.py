"""Application data stored by virtualenv."""

from __future__ import annotations

import logging
import os
import pathlib
import shutil
from contextlib import suppress
from stat import S_IMODE, S_ISGID, S_IWGRP, S_IWOTH
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
_MIGRATION_MARKER: Final = ".virtualenv-migration-incomplete"


def make_app_data(folder: str | None, *, read_only: bool, env: Mapping[str, str]) -> AppData:
    private: Final = folder is None and "VIRTUALENV_OVERRIDE_APP_DATA" not in env
    if folder is None:
        folder = _default_app_data_dir(env)
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
    if os.path.isdir(old_dir) and os.path.isfile(os.path.join(old_dir, _MIGRATION_MARKER)) and os.path.isdir(new_dir):
        _LOGGER.warning("incomplete app data migration from %s to %s, using old location", old_dir, new_dir)
        return old_dir
    if os.path.isdir(old_dir) and not os.path.isdir(new_dir):
        _LOGGER.info("migrating app data from %s to %s", old_dir, new_dir)
        try:
            if _is_nested_dir(new_dir, old_dir):
                # shutil.move cannot move a directory into its descendant.
                _migrate_into_nested(old_dir, new_dir)
            else:
                shutil.move(old_dir, new_dir)
        except OSError as exception:
            _LOGGER.warning(
                "could not migrate app data from %s to %s: %r, using old location", old_dir, new_dir, exception
            )
            return old_dir
    return new_dir


def _is_nested_dir(inner: str, outer: str) -> bool:
    try:
        return os.path.normcase(os.path.commonpath((outer, inner))) == os.path.normcase(outer)
    except ValueError:
        return False


def _migrate_into_nested(old_dir: str, new_dir: str) -> None:
    marker: Final = pathlib.Path(old_dir, _MIGRATION_MARKER)
    marker.touch(exist_ok=True)
    os.makedirs(new_dir, exist_ok=True)
    skipped_entries: Final = {os.path.relpath(new_dir, old_dir).split(os.sep, 1)[0], _MIGRATION_MARKER}
    moved: Final[list[str]] = []
    try:
        for entry in os.listdir(old_dir):
            if entry not in skipped_entries:
                shutil.move(os.path.join(old_dir, entry), new_dir)
                moved.append(entry)
    except OSError:
        if not sum(not _restore_nested_entry(entry, old_dir, new_dir) for entry in moved):
            with suppress(OSError):
                os.rmdir(new_dir)
        raise
    marker.unlink()


def _restore_nested_entry(entry: str, old_dir: str, new_dir: str) -> bool:
    try:
        shutil.move(os.path.join(new_dir, entry), old_dir)
    except OSError:
        return False
    return True


__all__ = (
    "AppDataDisabled",
    "AppDataDiskFolder",
    "ReadOnlyAppData",
    "TempAppData",
    "make_app_data",
)
