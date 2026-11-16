from __future__ import annotations

import logging
import os
import pathlib
import shutil
from contextlib import suppress
from typing import Final

from platformdirs import user_cache_dir, user_data_dir

_LOGGER: Final[logging.Logger] = logging.getLogger(__name__)
_MIGRATION_MARKER: Final[str] = ".virtualenv-migration-incomplete"


def cache_dir_with_migration() -> str:
    """Return the cache directory after migrating legacy app data when needed.

    :returns: the cache directory path

    """
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


__all__ = [
    "cache_dir_with_migration",
]
