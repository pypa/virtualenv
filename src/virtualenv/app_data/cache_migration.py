from __future__ import annotations

__lazy_modules__ = [
    "contextlib",
    "pathlib",
    "platformdirs",
    "shutil",
    "typing",
    "virtualenv.util.lock",
]

import logging
import os
import pathlib
import shutil
import stat
from contextlib import suppress
from typing import Final

from platformdirs import user_cache_dir, user_data_dir

from virtualenv.util.lock import ReentrantFileLock

_LOGGER: Final[logging.Logger] = logging.getLogger(__name__)
_MIGRATION_MARKER: Final[str] = ".virtualenv-migration-incomplete"
_CONFIG_NAME: Final[str] = "virtualenv.ini"
_CONFIG_MIGRATION_LOCK: Final[str] = ".virtualenv-migration"


def cache_dir_with_migration() -> str:
    """Return the cache directory after migrating legacy app data when needed.

    :returns: the cache directory path

    """
    new_dir: Final = user_cache_dir(appname="virtualenv", appauthor="pypa")
    old_dir: Final = user_data_dir(appname="virtualenv", appauthor="pypa")
    if new_dir == old_dir:
        return new_dir
    if os.path.lexists(os.path.join(old_dir, _CONFIG_NAME)):
        if not os.path.isdir(new_dir) or os.path.isfile(os.path.join(old_dir, _MIGRATION_MARKER)):
            _migrate_with_config(old_dir, new_dir)
        return new_dir
    if os.path.isdir(old_dir) and os.path.isfile(os.path.join(old_dir, _MIGRATION_MARKER)) and os.path.isdir(new_dir):
        _LOGGER.warning("incomplete app data migration from %s to %s, using old location", old_dir, new_dir)
        return old_dir
    if os.path.isdir(old_dir) and not os.path.isdir(new_dir):
        _LOGGER.info("migrating app data from %s to %s", old_dir, new_dir)
        try:
            nested: Final = _is_nested_dir(new_dir, old_dir)
            if nested:
                _migrate_entries(old_dir, new_dir, nested=True)
            else:
                shutil.move(old_dir, new_dir)
        except OSError as exception:
            _LOGGER.warning(
                "could not migrate app data from %s to %s: %r, using old location", old_dir, new_dir, exception
            )
            return old_dir
    return new_dir


def _migrate_with_config(old_dir: str, new_dir: str) -> None:
    # A reset must always select the cache path once the legacy directory is known to hold config.
    try:
        with ReentrantFileLock(old_dir).lock_for_key(_CONFIG_MIGRATION_LOCK):
            if not os.path.isdir(new_dir) or os.path.isfile(os.path.join(old_dir, _MIGRATION_MARKER)):
                _migrate_entries(old_dir, new_dir, nested=_is_nested_dir(new_dir, old_dir), keep_config=True)
    except OSError as exception:
        _LOGGER.warning("could not migrate app data from %s to %s: %r", old_dir, new_dir, exception)


def _is_nested_dir(inner: str, outer: str) -> bool:
    try:
        return os.path.normcase(os.path.commonpath((outer, inner))) == os.path.normcase(outer)
    except ValueError:
        return False


def _migrate_entries(old_dir: str, new_dir: str, *, nested: bool, keep_config: bool = False) -> None:
    marker: Final = pathlib.Path(old_dir, _MIGRATION_MARKER)
    marker.touch(exist_ok=True)
    os.makedirs(new_dir, mode=0o777 if nested else 0o700, exist_ok=True)
    skipped_entries: Final = {_MIGRATION_MARKER}
    if nested:
        skipped_entries.add(os.path.relpath(new_dir, old_dir).split(os.sep, 1)[0])
    if keep_config:
        skipped_entries.add(f"{_CONFIG_MIGRATION_LOCK}.lock")
    moved: Final[list[str]] = []
    try:
        if not nested and os.name == "posix":
            _preserve_cache_permissions(old_dir, new_dir)
        for entry in os.listdir(old_dir):
            if entry not in skipped_entries and (not keep_config or entry.casefold() != _CONFIG_NAME):
                shutil.move(os.path.join(old_dir, entry), new_dir)
                moved.append(entry)
    except OSError:
        if not sum(not _restore_nested_entry(entry, old_dir, new_dir) for entry in moved):
            with suppress(OSError):
                os.rmdir(new_dir)
        raise
    marker.unlink()


def _preserve_cache_permissions(old_dir: str, new_dir: str) -> None:
    old_info: Final = os.stat(old_dir)
    if os.stat(new_dir).st_gid != old_info.st_gid:
        os.chown(new_dir, -1, old_info.st_gid)
    os.chmod(new_dir, stat.S_IMODE(old_info.st_mode))


def _restore_nested_entry(entry: str, old_dir: str, new_dir: str) -> bool:
    try:
        shutil.move(os.path.join(new_dir, entry), old_dir)
    except OSError:
        return False
    return True


__all__ = [
    "cache_dir_with_migration",
]
