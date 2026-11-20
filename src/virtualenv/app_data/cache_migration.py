from __future__ import annotations

__lazy_modules__ = [
    "contextlib",
    "pathlib",
    "platformdirs",
    "shutil",
    "tempfile",
    "typing",
    "virtualenv.util.lock",
]

import logging
import os
import pathlib
import shutil
import stat
import tempfile
from contextlib import suppress
from typing import Final

from platformdirs import user_cache_dir, user_data_dir

from virtualenv.util.lock import ReentrantFileLock

_LOGGER: Final[logging.Logger] = logging.getLogger(__name__)
_MIGRATION_MARKER: Final[str] = ".virtualenv-migration-incomplete"
_CONFIG_NAME: Final[str] = "virtualenv.ini"
_CONFIG_MIGRATION_LOCK: Final[str] = ".virtualenv-migration"


def cache_dir_with_migration(*, read_only: bool) -> str:
    """Return the cache directory after migrating legacy app data when needed.

    :param read_only: whether the caller needs an existing directory

    :returns: the cache directory path

    """
    new_dir: Final[str] = user_cache_dir(appname="virtualenv", appauthor="pypa")
    old_dir: Final[str] = user_data_dir(appname="virtualenv", appauthor="pypa")
    if new_dir == old_dir:
        return new_dir
    if os.path.lexists(os.path.join(old_dir, _CONFIG_NAME)):
        if os.path.islink(old_dir):
            cache_ready = _copy_linked_cache(old_dir, new_dir)
        elif not os.path.isdir(new_dir) or os.path.isfile(os.path.join(old_dir, _MIGRATION_MARKER)):
            cache_ready = _migrate_with_config(old_dir, new_dir)
        else:
            cache_ready = True
        return old_dir if read_only and not cache_ready else new_dir
    if os.path.isdir(old_dir) and os.path.isfile(os.path.join(old_dir, _MIGRATION_MARKER)) and os.path.isdir(new_dir):
        _LOGGER.warning("incomplete app data migration from %s to %s, using old location", old_dir, new_dir)
        return old_dir
    if os.path.isdir(old_dir) and not os.path.isdir(new_dir):
        _LOGGER.info("migrating app data from %s to %s", old_dir, new_dir)
        try:
            nested: Final[bool] = _is_nested_dir(new_dir, old_dir)
            if nested:
                _migrate_entries(old_dir, new_dir, nested=True)
            else:
                _move_cache(old_dir, new_dir)
        except OSError as exception:
            _LOGGER.warning(
                "could not migrate app data from %s to %s: %r, using old location", old_dir, new_dir, exception
            )
            return old_dir
    return new_dir


def _copy_linked_cache(old_dir: str, new_dir: str) -> bool:
    marker = pathlib.Path(new_dir, _MIGRATION_MARKER)
    if os.path.isdir(new_dir) and not marker.exists():
        return True
    try:
        _prepare_linked_cache(old_dir, new_dir)
        marker.touch(exist_ok=True)
        _copy_linked_entries(old_dir, new_dir)
        marker.unlink()
    except OSError as exception:
        _LOGGER.warning("could not copy app data from %s to %s: %r", old_dir, new_dir, exception)
        return False
    else:
        return True


def _prepare_linked_cache(old_dir: str, new_dir: str) -> None:
    _prepare_cache_parent(old_dir, new_dir)
    os.makedirs(new_dir, mode=0o700, exist_ok=True)
    if os.name == "posix":
        info = os.stat(new_dir)
        if (mode := _migrated_cache_mode(info)) != stat.S_IMODE(info.st_mode):
            os.chmod(new_dir, mode)


def _prepare_cache_parent(old_dir: str, new_dir: str) -> None:
    if not os.stat(old_dir).st_mode & stat.S_ISGID:
        make_private_dirs(os.path.dirname(new_dir))


def make_private_dirs(folder: str) -> None:
    """Create missing path components with owner-only permissions.

    :param folder: target directory, including any missing parents

    :raises FileNotFoundError: if the filesystem root does not exist
    :raises NotADirectoryError: if a missing component becomes a file during creation

    """
    for path in _missing_dirs(folder):
        with suppress(FileExistsError):
            os.mkdir(path, 0o700)
        if not os.path.isdir(path):
            raise NotADirectoryError(path)


def _missing_dirs(folder: str) -> list[str]:
    missing: list[str] = []
    path = os.path.abspath(folder)
    while not os.path.exists(path):
        missing.append(path)
        parent = os.path.dirname(path)
        if parent == path:
            raise FileNotFoundError(path)
        path = parent
    return missing[::-1]


def _migrated_cache_mode(info: os.stat_result) -> int:
    return stat.S_IMODE(info.st_mode) & ~(stat.S_IRWXO if info.st_mode & stat.S_ISGID else stat.S_IRWXG | stat.S_IRWXO)


def _copy_linked_entries(old_dir: str, new_dir: str) -> None:
    skipped = {_CONFIG_NAME, _MIGRATION_MARKER, f"{_CONFIG_MIGRATION_LOCK}.lock"}
    if _is_nested_dir(os.path.realpath(new_dir), os.path.realpath(old_dir)):
        skipped.add(os.path.relpath(os.path.realpath(new_dir), os.path.realpath(old_dir)).split(os.sep, 1)[0])
    for entry in os.listdir(old_dir):
        if entry in skipped or entry.casefold() == _CONFIG_NAME:
            continue
        _copy_linked_entry(os.path.join(old_dir, entry), os.path.join(new_dir, entry))


def _copy_linked_entry(source: str, target: str) -> None:
    if os.path.islink(source):
        if os.path.lexists(target):
            os.unlink(target)
        os.symlink(os.readlink(source), target)
    elif os.path.isdir(source):
        if os.path.islink(target):
            os.unlink(target)
        os.makedirs(target, exist_ok=True)
        for entry in os.listdir(source):
            _copy_linked_entry(os.path.join(source, entry), os.path.join(target, entry))
    else:
        with tempfile.NamedTemporaryFile(dir=os.path.dirname(target), delete=False) as temporary:
            temp_path = temporary.name
        try:
            shutil.copy2(source, temp_path)
            os.replace(temp_path, target)
        finally:
            with suppress(FileNotFoundError):
                os.unlink(temp_path)


def _migrate_with_config(old_dir: str, new_dir: str) -> bool:
    # A reset must always select the cache path once the legacy directory is known to hold config.
    try:
        with ReentrantFileLock(old_dir).lock_for_key(_CONFIG_MIGRATION_LOCK):
            if not os.path.isdir(new_dir) or os.path.isfile(os.path.join(old_dir, _MIGRATION_MARKER)):
                _migrate_entries(old_dir, new_dir, nested=_is_nested_dir(new_dir, old_dir), keep_config=True)
    except OSError as exception:
        _LOGGER.warning("could not migrate app data from %s to %s: %r", old_dir, new_dir, exception)
        return False
    else:
        return True


def _is_nested_dir(inner: str, outer: str) -> bool:
    try:
        return os.path.normcase(os.path.commonpath((outer, inner))) == os.path.normcase(outer)
    except ValueError:
        return False


def _migrate_entries(old_dir: str, new_dir: str, *, nested: bool, keep_config: bool = False) -> None:
    marker: Final[pathlib.Path] = pathlib.Path(old_dir, _MIGRATION_MARKER)
    marker.touch(exist_ok=True)
    if nested:
        old_info: Final[os.stat_result] = os.stat(old_dir)
        if os.name == "posix" and old_info.st_mode & stat.S_ISGID:
            _make_shared_dirs(new_dir, old_info.st_gid)
        else:
            make_private_dirs(new_dir)
    else:
        _prepare_cache_parent(old_dir, new_dir)
        os.makedirs(new_dir, mode=0o700, exist_ok=True)
    skipped_entries: Final[set[str]] = {_MIGRATION_MARKER}
    if nested:
        skipped_entries.add(os.path.relpath(new_dir, old_dir).split(os.sep, 1)[0])
    if keep_config:
        skipped_entries.add(f"{_CONFIG_MIGRATION_LOCK}.lock")
    moved: Final[list[str]] = []
    try:
        if not nested and os.name == "posix":
            _preserve_cache_permissions(old_dir, new_dir)
        for entry in os.listdir(old_dir):
            if (
                entry not in skipped_entries
                and (not keep_config or entry.casefold() != _CONFIG_NAME)
                and _move_cache_entry(os.path.join(old_dir, entry), os.path.join(new_dir, entry))
            ):
                moved.append(entry)
    except OSError:
        if not sum(not _restore_nested_entry(entry, old_dir, new_dir) for entry in moved):
            with suppress(OSError):
                os.rmdir(new_dir)
        raise
    marker.unlink()


def _make_shared_dirs(folder: str, group: int) -> None:
    for path in _missing_dirs(folder):
        os.mkdir(path, 0o700)
        if os.stat(path).st_gid != group:
            os.chown(path, -1, group)
        # macOS does not inherit setgid through newly created intermediate directories.
        os.chmod(path, stat.S_ISGID | stat.S_IRWXU | stat.S_IRWXG)  # ruff:ignore[bad-file-permissions]  # shared cache


def _preserve_cache_permissions(old_dir: str, new_dir: str) -> None:
    old_info: Final[os.stat_result] = os.stat(old_dir)
    if os.stat(new_dir).st_gid != old_info.st_gid:
        os.chown(new_dir, -1, old_info.st_gid)
    os.chmod(new_dir, _migrated_cache_mode(old_info))


def _move_cache_entry(source: str, target: str) -> bool:
    if not os.path.lexists(target):
        shutil.move(source, target)
        return True
    if os.path.isdir(source) and not os.path.islink(source) and os.path.isdir(target) and not os.path.islink(target):
        for entry in os.listdir(source):
            _move_cache_entry(os.path.join(source, entry), os.path.join(target, entry))
        with suppress(OSError):
            os.rmdir(source)
    elif (
        os.path.isfile(source) and not os.path.islink(source) and os.path.isfile(target) and not os.path.islink(target)
    ):
        with tempfile.NamedTemporaryFile(dir=os.path.dirname(target), delete=False) as temporary:
            temp_path = temporary.name
        try:
            shutil.copy2(source, temp_path)
            os.replace(temp_path, target)
        finally:
            with suppress(FileNotFoundError):
                os.unlink(temp_path)
        os.unlink(source)
    else:
        msg = f"cannot merge app data entry {source} into {target}"
        raise OSError(msg)
    return False


def _restore_nested_entry(entry: str, old_dir: str, new_dir: str) -> bool:
    try:
        shutil.move(os.path.join(new_dir, entry), old_dir)
    except OSError:
        return False
    return True


def _move_cache(old_dir: str, new_dir: str) -> None:
    _prepare_cache_parent(old_dir, new_dir)
    if os.name != "posix" or os.path.islink(old_dir):
        shutil.move(old_dir, new_dir)
        return
    old_info = os.stat(old_dir)
    if (mode := _migrated_cache_mode(old_info)) != stat.S_IMODE(old_info.st_mode):
        os.chmod(old_dir, mode)
    try:
        os.rename(old_dir, new_dir)
    except OSError:
        # shutil.move creates the copy with the umask before copying the private source mode.
        os.makedirs(new_dir, mode=0o700)
        try:
            if old_info.st_mode & stat.S_ISGID and os.stat(new_dir).st_gid != old_info.st_gid:
                os.chown(new_dir, -1, old_info.st_gid)
            shutil.copytree(old_dir, new_dir, symlinks=True, dirs_exist_ok=True)
            _preserve_cache_permissions(old_dir, new_dir)
        except OSError:
            with suppress(OSError):
                shutil.rmtree(new_dir)
            raise
        shutil.rmtree(old_dir)


__all__ = [
    "cache_dir_with_migration",
    "make_private_dirs",
]
