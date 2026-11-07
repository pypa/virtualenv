"""Periodically update bundled versions."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import ssl
import sys
from contextlib import suppress
from datetime import datetime, timedelta, timezone
from itertools import groupby
from pathlib import Path
from shutil import copy2
from subprocess import DEVNULL, Popen
from textwrap import dedent, indent
from threading import Thread
from time import sleep
from typing import TYPE_CHECKING, Final
from urllib.error import URLError
from urllib.request import urlopen

from virtualenv.app_data import AppDataDiskFolder
from virtualenv.config.convert import BoolType
from virtualenv.config.env_var import get_env_var
from virtualenv.info import IS_ZIPAPP, ROOT
from virtualenv.util.subprocess import CREATE_NO_WINDOW

from .embed import BUNDLE_SUPPORT
from .util import Wheel

if TYPE_CHECKING:
    from collections.abc import Generator

    from virtualenv.app_data.base import AppData, ContentStore

LOGGER: Final[logging.Logger] = logging.getLogger(__name__)
GRACE_PERIOD_CI: Final[timedelta] = timedelta(hours=1)  # prevent version switch in the middle of a CI run
GRACE_PERIOD_MINOR: Final[timedelta] = timedelta(days=28)
UPDATE_PERIOD: Final[timedelta] = timedelta(days=14)
UPDATE_ABORTED_DELAY: Final[timedelta] = timedelta(hours=1)


# from_bundle passes these inputs through, and the update needs each one
def periodic_update(  # ruff:ignore[too-many-arguments]
    distribution: str,
    of_version: str | None,
    for_py_version: str,
    wheel: Wheel | None,
    search_dirs: list[Path],
    app_data: AppData,
    do_periodic_update: bool,
    env: dict[str, str],
) -> Wheel | None:
    """Return the wheel to seed with, starting a background update of the bundled wheels when one is due.

    :param distribution: the distribution name
    :param of_version: the version requested, ``None`` for the newest
    :param for_py_version: the Python version the wheel must support
    :param wheel: the wheel found so far, ``None`` when none was found
    :param search_dirs: the folders searched for wheels
    :param app_data: the application data folder
    :param do_periodic_update: ``True`` to check for updates in the background
    :param env: the environment variables for the update

    :returns: the wheel to seed with, possibly a newer one that was already downloaded

    """
    if do_periodic_update:
        handle_auto_update(distribution, for_py_version, wheel, search_dirs, app_data, env)

    now = datetime.now(tz=timezone.utc)

    def _update_wheel(ver: NewVersion) -> Wheel:
        updated_wheel = Wheel(app_data.house / ver.filename)
        LOGGER.debug("using %supdated wheel %s", "periodically " if updated_wheel else "", updated_wheel)
        return updated_wheel

    u_log = UpdateLog.from_app_data(app_data, distribution, for_py_version)
    if of_version is None:
        for _, group in groupby(u_log.versions, key=lambda entry: entry.wheel.version_tuple[0:2]):
            # use only latest patch version per minor, earlier assumed to be buggy
            all_patches = list(group)
            ignore_grace_period_minor = any(version for version in all_patches if version.use(now))
            for version in all_patches:
                if wheel is not None and version.wheel.parsed_version <= wheel.parsed_version:
                    return wheel
                if version.use(now, ignore_grace_period_minor):
                    return _update_wheel(version)
    else:
        for version in u_log.versions:
            if version.wheel.has_version(of_version):
                return _update_wheel(version)

    return wheel


# same inputs as periodic_update, forwarded to trigger_update
def handle_auto_update(  # ruff:ignore[too-many-arguments]
    distribution: str,
    for_py_version: str,
    wheel: Wheel | None,
    search_dirs: list[Path],
    app_data: AppData,
    env: dict[str, str],
) -> None:
    u_log = UpdateLog.from_app_data(app_data, distribution, for_py_version)
    if u_log.needs_update:
        u_log.periodic = True
        u_log.started = datetime.now(tz=timezone.utc)
        app_data.embed_update_log(distribution, for_py_version).write(u_log.to_dict())
        trigger_update(distribution, for_py_version, wheel, search_dirs, app_data, periodic=True, env=env)


def trigger_update(  # ruff:ignore[too-many-arguments]  # the background update process needs every input
    distribution: str,
    for_py_version: str,
    wheel: Wheel | None,
    search_dirs: list[Path],
    app_data: AppData,
    env: dict[str, str],
    periodic: bool,
) -> None:
    """Start a background process that updates the wheels of a distribution.

    :param distribution: the distribution name
    :param for_py_version: the Python version the wheel must support
    :param wheel: the wheel to update, ``None`` when none was found
    :param search_dirs: the folders searched for wheels
    :param app_data: the application data folder
    :param env: the environment variables for the update
    :param periodic: ``True`` when the update is a periodic check rather than a manual one

    """
    wheel_path = None if wheel is None else str(wheel.path)
    code = (
        dedent(
            """\
        from virtualenv.report import setup_report, MAX_LEVEL
        from virtualenv.seed.wheels.periodic_update import do_update
        setup_report(MAX_LEVEL, show_pid=True)
        do_update({!r}, {!r}, {!r}, {!r}, {!r}, {!r})
        """
        )
        .strip()
        .format(distribution, for_py_version, wheel_path, str(app_data), [str(p) for p in search_dirs], periodic)
    )
    code = (
        f"import runpy\nwith runpy.run_path({ROOT!r}, run_name='__loader__')['VersionedFindLoad']():\n{indent(code, '    ')}"
        if IS_ZIPAPP
        else "import importlib.util\n"
        f"spec = importlib.util.spec_from_file_location('virtualenv', {str(Path(ROOT) / 'virtualenv' / '__init__.py')!r})\n"
        "package = importlib.util.module_from_spec(spec)\n"
        "sys.modules['virtualenv'] = package\n"
        "spec.loader.exec_module(package)\n"
        f"{code}"
    )
    # drop the implicit working-directory entry before anything else is imported, as sys is built in
    cmd: Final = [sys.executable, "-c", f"import sys\nsys.path = [p for p in sys.path if p]\n{code}"]
    debug = env.get("_VIRTUALENV_PERIODIC_UPDATE_INLINE") == "1"
    pipe = None if debug else DEVNULL
    kwargs = {"stdout": pipe, "stderr": pipe}
    if not debug and sys.platform == "win32":
        kwargs["creationflags"] = CREATE_NO_WINDOW
    # kwargs mixes pipe and creationflags, which ty cannot match to one Popen overload
    process = Popen(cmd, **kwargs)  # ty: ignore[no-matching-overload]
    LOGGER.info(
        "triggered periodic upgrade of %s%s (for python %s) via background process having PID %d",
        distribution,
        "" if wheel is None else f"=={wheel.version}",
        for_py_version,
        process.pid,
    )
    if debug:
        process.communicate()  # on purpose not called to make it a background process
    else:
        # set the returncode here -> no ResourceWarning on main process exit if the subprocess still runs
        process.returncode = 0


def add_wheel_to_update_log(wheel: Wheel, for_py_version: str, app_data: AppData) -> None:
    """Record a wheel in the update log of its distribution, unless the log already names it.

    :param wheel: the wheel to record
    :param for_py_version: the Python version the wheel must support
    :param app_data: the application data folder

    """
    embed_update_log = app_data.embed_update_log(wheel.distribution, for_py_version)
    # the disk store has a file attribute that ContentStore does not declare
    LOGGER.debug("adding %s information to %s", wheel.name, embed_update_log.file)  # ty: ignore[unresolved-attribute]
    u_log = UpdateLog.from_app_data(app_data, wheel.distribution, for_py_version)
    if any(version.filename == wheel.name for version in u_log.versions):
        # the disk store has a file attribute that ContentStore does not declare
        LOGGER.warning("%s already present in %s", wheel.name, embed_update_log.file)  # ty: ignore[unresolved-attribute]
        return
    # we don't need a release date for sources other than "periodic"
    version = NewVersion(wheel.name, datetime.now(tz=timezone.utc), None, "download")
    u_log.versions.append(version)  # always write at the end for proper updates
    embed_update_log.write(u_log.to_dict())


DATETIME_FMT: Final[str] = "%Y-%m-%dT%H:%M:%S.%fZ"


def dump_datetime(value: datetime | None) -> str | None:
    """Format a datetime for the update log, keeping ``None`` as ``None``.

    :param value: the datetime to format

    :returns: the formatted text, ``None`` for ``None``

    """
    return None if value is None else value.strftime(DATETIME_FMT)


def load_datetime(value: str | None) -> datetime | None:
    """Parse a datetime written by :func:`dump_datetime`, as UTC.

    :param value: the text to parse, ``None`` for no datetime

    :returns: the UTC datetime, ``None`` for ``None``

    """
    return None if value is None else datetime.strptime(value, DATETIME_FMT).replace(tzinfo=timezone.utc)


# source is reassigned after creation, so instances must not be hashed
class NewVersion:  # ruff:ignore[eq-without-hash]
    """A wheel version found by an update, with where it came from and when it was found.

    :param filename: the wheel file name
    :param found_date: when the version was found
    :param release_date: when the version was released, ``None`` when unknown
    :param source: where the version came from, ``manual``, ``periodic`` or ``download``

    """

    def __init__(self, filename: str, found_date: datetime, release_date: datetime | None, source: str) -> None:
        self.filename = filename
        self.found_date = found_date
        self.release_date = release_date
        self.source = source

    @classmethod
    def from_dict(cls, dictionary: dict[str, str | None]) -> NewVersion:
        """Parse a version from the stored form of the update log.

        :param dictionary: the stored form of the version

        :returns: the version

        """
        return cls(
            # the JSON value is typed str | None, but the constructor needs str
            filename=dictionary["filename"],  # ty: ignore[invalid-argument-type]
            # load_datetime returns datetime | None, and found_date is never None here
            found_date=load_datetime(dictionary["found_date"]),  # ty: ignore[invalid-argument-type]
            release_date=load_datetime(dictionary["release_date"]),
            # the JSON value is typed str | None, but the constructor needs str
            source=dictionary["source"],  # ty: ignore[invalid-argument-type]
        )

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}(filename={self.filename}), found_date={self.found_date}, "
            f"release_date={self.release_date}, source={self.source})"
        )

    def __eq__(self, other: object) -> bool:
        # exact type match on purpose, so a subclass never compares equal
        return type(self) == type(other) and all(  # ruff:ignore[type-comparison]
            getattr(self, k) == getattr(other, k) for k in ["filename", "release_date", "found_date", "source"]
        )

    def __ne__(self, other: object) -> bool:
        return not (self == other)

    @property
    def wheel(self) -> Wheel:
        """The wheel file of the version."""
        return Wheel(Path(self.filename))

    def to_dict(self) -> dict[str, str | None]:
        """Return the stored form of the version, for the update log.

        :returns: the version as a dictionary of text values

        """
        return {
            "filename": self.filename,
            "release_date": dump_datetime(self.release_date),
            "found_date": dump_datetime(self.found_date),
            "source": self.source,
        }

    # line 74 passes the minor flag positionally, line 479 passes ci by name
    def use(self, now: datetime, ignore_grace_period_minor: bool = False, ignore_grace_period_ci: bool = False) -> bool:  # ruff:ignore[boolean-default-value-positional-argument]
        """Whether the version should be used at the given time, once its grace period has passed.

        :param now: the current time
        :param ignore_grace_period_minor: ``True`` to use the version without waiting for its minor release grace period
        :param ignore_grace_period_ci: ``True`` to use the version without waiting for the CI grace period

        :returns: ``True`` when the version can be used

        """
        if self.source == "manual":
            return True
        if self.source == "periodic" and (self.found_date < now - GRACE_PERIOD_CI or ignore_grace_period_ci):
            if not ignore_grace_period_minor:
                return now - (self.release_date or self.found_date) >= GRACE_PERIOD_MINOR
            return True
        return False


class UpdateLog:
    """The record of the last update of a distribution, with the versions it found.

    :param started: when the last update started, ``None`` when it never did
    :param completed: when the last update completed, ``None`` when it never did
    :param versions: the versions found
    :param periodic: ``True`` when the update was periodic, ``None`` when unknown

    """

    def __init__(
        self, started: datetime | None, completed: datetime | None, versions: list[NewVersion], periodic: bool | None
    ) -> None:
        self.started = started
        self.completed = completed
        self.versions = versions
        self.periodic = periodic

    @classmethod
    def from_app_data(cls, app_data: AppData, distribution: str, for_py_version: str) -> UpdateLog:
        """Load the update log of a distribution from the application data folder.

        :param app_data: the application data folder
        :param distribution: the distribution name
        :param for_py_version: the Python version the log is for

        :returns: the update log, empty when none was stored

        """
        store: Final[ContentStore] = app_data.embed_update_log(distribution, for_py_version)
        try:
            return cls.from_dict(store.read())
        except (AttributeError, KeyError, TypeError, ValueError):
            # another virtualenv version or an interrupted run can leave valid JSON of the wrong shape in the shared
            # app data; drop it as read() drops invalid JSON, since an empty log falls back to the bundled wheel
            LOGGER.warning("removing malformed embed update log of %s", distribution)
            with suppress(OSError):  # another process may remove or rewrite the file at the same time
                store.remove()
            return cls(None, None, [], None)

    @classmethod
    def from_dict(cls, dictionary: dict[str, object] | None) -> UpdateLog:
        """Parse the update log from the stored form.

        :param dictionary: the stored form of the update log, ``None`` when none was stored

        :returns: the update log

        """
        if dictionary is None:
            dictionary = {}
        return cls(
            # the log is parsed JSON, typed object, so the value is not narrowed
            load_datetime(dictionary.get("started")),  # ty: ignore[invalid-argument-type]
            # the log is parsed JSON, typed object, so the value is not narrowed
            load_datetime(dictionary.get("completed")),  # ty: ignore[invalid-argument-type]
            # the log is parsed JSON, typed object, so the list is not narrowed
            [NewVersion.from_dict(v) for v in dictionary.get("versions", [])],  # ty: ignore[not-iterable]
            # the log is parsed JSON, typed object, so the value is not narrowed
            dictionary.get("periodic"),  # ty: ignore[invalid-argument-type]
        )

    @property
    def needs_update(self) -> bool:
        """Whether an update is due: none has completed, or the last completion is older than the update period."""
        now = datetime.now(tz=timezone.utc)
        if self.completed is None:  # never completed
            return self._check_start(now)
        if now - self.completed <= UPDATE_PERIOD:
            return False
        return self._check_start(now)

    def _check_start(self, now: datetime) -> bool:
        return self.started is None or now - self.started > UPDATE_ABORTED_DELAY

    def to_dict(self) -> dict[str, object]:
        """Return the stored form of the update log.

        :returns: the update log as a dictionary

        """
        return {
            "started": dump_datetime(self.started),
            "completed": dump_datetime(self.completed),
            "periodic": self.periodic,
            "versions": [r.to_dict() for r in self.versions],
        }


#: Pauses between PyPI metadata lookups before refusing a wheel we could not verify, to ride out a brief outage or a JSON
#: API that has not caught up with a fresh upload.
_DIGEST_RETRY_DELAYS: Final[tuple[float, ...]] = (1.0, 2.0, 4.0)


def verify_wheel_digest(wheel: Wheel) -> None:
    """Verify a downloaded wheel's sha256 against the digest PyPI's JSON API reports for that release.

    ``pip download`` trusts whatever index it is configured to use, and nothing else in this module checks the bytes it
    hands back. Callers run this only when pip used the default index, so PyPI served the file and must list its digest.
    A failed metadata request, an unknown filename or a missing sha256 therefore fails like a mismatch: accepting the
    wheel in those cases would let anyone who can block ``pypi.org/pypi`` turn the check off.

    :param wheel: the downloaded wheel to verify

    :raises UnverifiedWheelError: if PyPI's sha256 for this exact filename cannot be obtained after retrying.
    :raises RuntimeError: if the sha256 does not match.

    """
    expected = _pypi_sha256_for_wheel(wheel)
    for delay in _DIGEST_RETRY_DELAYS:
        if expected is not None:
            break
        LOGGER.warning("could not obtain the sha256 of %s from PyPI, retrying in %s seconds", wheel.name, delay)
        _PYPI_CACHE.pop(wheel.distribution, None)
        sleep(delay)
        expected = _pypi_sha256_for_wheel(wheel)
    if expected is None:
        msg = f"refusing downloaded wheel {wheel.name}: could not obtain its sha256 from PyPI to verify it"
        raise UnverifiedWheelError(msg)
    if (actual := hashlib.sha256(wheel.path.read_bytes()).hexdigest()) != expected:
        msg = f"downloaded wheel {wheel.name} has sha256 {actual}, but PyPI reports {expected} for this release"
        raise RuntimeError(msg)


def _pypi_sha256_for_wheel(wheel: Wheel) -> str | None:
    content = _pypi_get_distribution_info_cached(wheel.distribution)
    releases = content.get("releases") if isinstance(content, dict) else None
    entries = releases.get(wheel.version) if isinstance(releases, dict) else None
    if not isinstance(entries, list):
        return None
    entry = next((entry for entry in entries if isinstance(entry, dict) and entry.get("filename") == wheel.name), {})
    digests = entry.get("digests")
    sha256 = digests.get("sha256") if isinstance(digests, dict) else None
    return sha256 if isinstance(sha256, str) else None


def _pypi_get_distribution_info_cached(distribution: str) -> dict[str, object] | None:
    if distribution not in _PYPI_CACHE:
        _PYPI_CACHE[distribution] = _pypi_get_distribution_info(distribution)
    return _PYPI_CACHE[distribution]


def _pypi_get_distribution_info(distribution: str) -> dict[str, object] | None:
    content, url = None, f"https://pypi.org/pypi/{distribution}/json"
    try:
        for context in _request_context():
            if (content := _fetch_pypi_json(url, context)) is not None:
                break
    # a failed metadata lookup is logged and treated as unavailable, not raised
    except Exception as exception:  # ruff:ignore[blind-except]
        # the log line carries the exception repr, a traceback adds nothing
        LOGGER.error("failed to access %s because %r", url, exception)  # ruff:ignore[error-instead-of-exception]
    return content


def _request_context() -> Generator[ssl.SSLContext | None, None, None]:
    yield None
    if (setting := get_env_var("periodic_update_insecure", BoolType(bool, bool), os.environ)) and setting[0]:
        LOGGER.warning(
            "falling back to unverified HTTPS for PyPI metadata because VIRTUALENV_PERIODIC_UPDATE_INSECURE is enabled",
        )
        # the private helper is the only way to build an unverified context, opt-in only
        yield ssl._create_unverified_context()  # ruff:ignore[suspicious-unverified-context-usage, private-member-access]


def _fetch_pypi_json(url: str, context: ssl.SSLContext | None) -> dict[str, object] | None:
    try:
        # url is a fixed https://pypi.org address, not user input
        with urlopen(url, context=context) as file_handler:  # ruff:ignore[suspicious-url-open-usage]
            return json.load(file_handler)
    except URLError as exception:
        # the log line carries the exception repr, a traceback adds nothing
        LOGGER.error("failed to access %s because %r", url, exception)  # ruff:ignore[error-instead-of-exception]
    return None


class UnverifiedWheelError(RuntimeError):
    """PyPI's digest for a downloaded wheel was unavailable, so a caller may fall back to the bundled wheel."""


_PYPI_CACHE: Final[dict[str, dict[str, object] | None]] = {}


def manual_upgrade(app_data: AppData, env: dict[str, str]) -> None:
    """Update the bundled wheels of every supported Python version now, in parallel.

    :param app_data: the application data folder
    :param env: the environment variables for the update

    """
    threads = []

    for for_py_version, distribution_to_package in BUNDLE_SUPPORT.items():
        # load extra search dir for the given for_py
        for distribution in distribution_to_package:
            thread = Thread(target=_run_manual_upgrade, args=(app_data, distribution, for_py_version, env))
            thread.start()
            threads.append(thread)

    for thread in threads:
        thread.join()


def _run_manual_upgrade(app_data: AppData, distribution: str, for_py_version: str, env: dict[str, str]) -> None:
    start = datetime.now(tz=timezone.utc)
    # bundle imports this module, so the import must wait until it is needed
    from .bundle import from_bundle  # ruff:ignore[import-outside-top-level]

    current = from_bundle(
        distribution=distribution,
        version=None,
        for_py_version=for_py_version,
        search_dirs=[],
        app_data=app_data,
        do_periodic_update=False,
        env=env,
    )
    LOGGER.warning(
        "upgrade %s for python %s with current %s",
        distribution,
        for_py_version,
        "" if current is None else current.name,
    )
    versions = do_update(
        distribution=distribution,
        for_py_version=for_py_version,
        # the bundled wheel exists for every distribution a manual upgrade runs on
        embed_filename=current.path,  # ty: ignore[invalid-argument-type, unresolved-attribute]
        app_data=app_data,
        search_dirs=[],
        periodic=False,
    )

    args = [
        distribution,
        for_py_version,
        datetime.now(tz=timezone.utc) - start,
    ]
    if versions:
        args.append("\n".join(f"\t{v}" for v in versions))
    ver_update = "new entries found:\n%s" if versions else "no new versions found"
    msg = f"upgraded %s for python %s in %s {ver_update}"
    LOGGER.warning(msg, *args)


# the subprocess entry point takes the same six inputs as the generated call
def do_update(  # ruff:ignore[too-many-arguments]
    distribution: str,
    for_py_version: str,
    embed_filename: str | None,
    app_data: str | AppData,
    search_dirs: list[str] | list[Path],
    periodic: bool,
) -> list[NewVersion] | None:
    """Download the newest wheel of a distribution and record it in the update log.

    :param distribution: the distribution name
    :param for_py_version: the Python version the wheel must support
    :param embed_filename: the bundled wheel file name, ``None`` when there is none
    :param app_data: the application data folder, or its path
    :param search_dirs: the folders searched for wheels
    :param periodic: ``True`` when the update is a periodic check rather than a manual one

    :returns: the versions downloaded, ``None`` when the update did not run

    """
    versions = None
    try:
        versions = _run_do_update(app_data, distribution, embed_filename, for_py_version, periodic, search_dirs)
    finally:
        LOGGER.debug("done %s %s with %s", distribution, for_py_version, versions)
    return versions


# one update pass; the download loop shares its state with the log bookkeeping
def _run_do_update(  # ruff:ignore[complex-structure, too-many-arguments]
    app_data: str | AppData,
    distribution: str,
    embed_filename: str | None,
    for_py_version: str,
    periodic: bool,
    search_dirs: list[str] | list[Path],
) -> list[NewVersion]:
    # acquire imports this module, so the import must wait until it is needed
    from . import acquire  # ruff:ignore[import-outside-top-level]

    wheel_filename = None if embed_filename is None else Path(embed_filename)
    embed_version = None if wheel_filename is None else Wheel(wheel_filename).parsed_version
    app_data = AppDataDiskFolder(app_data) if isinstance(app_data, str) else app_data
    search_dirs = [Path(p) if isinstance(p, str) else p for p in search_dirs]
    wheelhouse = app_data.house
    u_log = UpdateLog.from_app_data(app_data, distribution, for_py_version)
    now = datetime.now(tz=timezone.utc)

    update_versions, other_versions = [], []
    for version in u_log.versions:
        if version.source in {"periodic", "manual"}:
            update_versions.append(version)
        else:
            other_versions.append(version)

    if periodic:
        source = "periodic"
    else:
        source = "manual"
        # mark the most recent one as source "manual"
        if update_versions:
            update_versions[0].source = source

    if wheel_filename is not None:
        dest = wheelhouse / wheel_filename.name
        if not dest.exists():
            copy2(str(wheel_filename), str(wheelhouse))
    last, last_version, versions, filenames = None, None, [], set()
    while last is None or not last.use(now, ignore_grace_period_ci=True):
        download_time = datetime.now(tz=timezone.utc)
        dest = acquire.download_wheel(
            distribution=distribution,
            version_spec=None if last_version is None else f"<{last_version}",
            for_py_version=for_py_version,
            search_dirs=search_dirs,
            app_data=app_data,
            to_folder=wheelhouse,
            env=os.environ,  # ty: ignore[invalid-argument-type]  # os.environ is a Mapping, not a dict
        )
        if (
            dest is None
            or (update_versions and update_versions[0].filename == dest.name)
            or (embed_version is not None and dest.parsed_version < embed_version)
        ):
            break
        release_date = release_date_for_wheel_path(dest.path)
        last = NewVersion(filename=dest.path.name, release_date=release_date, found_date=download_time, source=source)
        LOGGER.info("detected %s in %s", last, datetime.now(tz=timezone.utc) - download_time)
        versions.append(last)
        filenames.add(last.filename)
        last_wheel = last.wheel
        last_version = last_wheel.version
        if embed_version is not None and embed_version >= last_wheel.parsed_version:
            break  # stop download if we reach the embed version
    u_log.periodic = periodic
    if not u_log.periodic:
        u_log.started = now
    # update other_versions by removing version we just found
    other_versions = [version for version in other_versions if version.filename not in filenames]
    u_log.versions = versions + update_versions + other_versions
    u_log.completed = datetime.now(tz=timezone.utc)
    app_data.embed_update_log(distribution, for_py_version).write(u_log.to_dict())
    return versions


def release_date_for_wheel_path(dest: Path) -> datetime | None:
    """Return the release date of a wheel from the package index, ``None`` when it is unknown.

    :param dest: the path of the wheel file

    :returns: the release date in UTC, ``None`` when the index does not know it

    """
    wheel = Wheel(dest)
    # the most accurate is to ask PyPi - e.g. https://pypi.org/pypi/pip/json,
    # see https://warehouse.pypa.io/api-reference/json/ for more details
    if (content := _pypi_get_distribution_info_cached(wheel.distribution)) is not None:
        try:
            # content is parsed JSON, so the subscripts are not type checked
            upload_time = content["releases"][wheel.version][0]["upload_time"]  # ty: ignore[not-subscriptable]
            return datetime.strptime(upload_time, "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
        # a malformed release record must not abort the update, the error is logged
        except Exception as exception:  # ruff:ignore[blind-except]
            # the log line carries the exception repr, a traceback adds nothing
            LOGGER.error("could not load release date %s because %r", content, exception)  # ruff:ignore[error-instead-of-exception]
    return None


__all__ = [
    "NewVersion",
    "UnverifiedWheelError",
    "UpdateLog",
    "add_wheel_to_update_log",
    "do_update",
    "dump_datetime",
    "load_datetime",
    "manual_upgrade",
    "periodic_update",
    "release_date_for_wheel_path",
    "trigger_update",
    "verify_wheel_digest",
]
