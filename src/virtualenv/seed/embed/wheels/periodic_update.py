"""
Periodically update bundled versions.
"""

import calendar
import json
import logging
import subprocess
import sys
import tempfile
from contextlib import contextmanager
from datetime import datetime, timedelta
from shutil import copy2

from six.moves.urllib.request import urlopen

from virtualenv.seed.embed.wheels.util import Wheel
from virtualenv.util.lock import ReentrantFileLock, Timeout
from virtualenv.util.path import Path, safe_delete
from virtualenv.util.subprocess import DETACHED_PROCESS, Popen


def periodic_update(distribution, for_py_version, wheel, cache_dir, app_data):
    if distribution != "pip":
        raise RuntimeError("only pip may be periodically updated")

    needs_update = False
    with update_log_for_distribution(cache_dir.parent, distribution, no_block=True) as update_log:
        if update_log.needs_update:
            update_log.started = datetime.now()
            update_log.update()
            needs_update = True
    if needs_update:
        trigger_update(distribution, for_py_version, wheel, app_data)
    # TODO: only upgrade when an hour passed since periodic update - to keep most CI stable
    for version in update_log.versions:
        if version.filename is None or version.filename == wheel.name:
            continue
        updated_wheel = Wheel(cache_dir / version.filename)
        # use it only if released long enough time ago - use version number to approximate release
        # only use if it has been released for at least 28 days
        if datetime.now() - version.release_date > timedelta(days=28):
            logging.debug("using periodically updated wheel %s", updated_wheel)
            return updated_wheel
    return wheel


@contextmanager
def update_log_for_distribution(folder, distribution, no_block=False):
    root_lock, lock_name = ReentrantFileLock(folder), "{}.update.lock".format(distribution)
    try:
        with root_lock.lock_for_key(lock_name, no_block=no_block):
            update_log = UpdateLog.from_path(folder / "{}.update.json".format(distribution))
            yield update_log
    except Timeout:
        return


DATETIME_FMT = "%Y-%m-%dT%H:%M:%SZ"


def dump_datetime(value):
    if value is None:
        return None
    return datetime.strftime(value, DATETIME_FMT)


def load_datetime(value):
    if value is None:
        return None
    return datetime.strptime(value, DATETIME_FMT)


class NewVersion(object):
    def __init__(self, filename, release_date):
        self.filename = filename
        self.release_date = release_date

    @classmethod
    def from_dict(cls, dictionary):
        return cls(filename=dictionary["filename"], release_date=load_datetime(dictionary["release_date"]))

    def to_dict(self):
        return {
            "filename": self.filename,
            "release_date": dump_datetime(self.release_date),
        }


class UpdateLog(object):
    def __init__(self, path, started, completed, versions):
        self.path = path
        self.started = started
        self.completed = completed
        self.versions = versions

    @classmethod
    def from_dict(cls, path, dictionary):
        return cls(
            path,
            load_datetime(dictionary.get("started")),
            load_datetime(dictionary.get("completed")),
            [NewVersion.from_dict(v) for v in dictionary.get("versions", [])],
        )

    @classmethod
    def from_path(cls, path):
        content = {}
        if path.exists():
            try:
                with open(str(path), "rt") as file_handler:
                    content = json.load(file_handler)
            except (IOError, ValueError):
                pass
        return cls.from_dict(path, content)

    def to_dict(self):
        return {
            "started": dump_datetime(self.started),
            "completed": dump_datetime(self.completed),
            "versions": [r.to_dict() for r in self.versions],
        }

    def update(self):
        with open(str(self.path), "wt") as file_handler:
            json.dump(self.to_dict(), file_handler, sort_keys=True, indent=4)

    @property
    def needs_update(self):
        now = datetime.now()
        if self.completed is None:  # never completed
            return self._check_start(now)
        else:
            if now - self.completed <= timedelta(days=14):
                return False
            return self._check_start(now)

    def _check_start(self, now):
        return self.started is None or now - self.started >= timedelta(hours=1)


def trigger_update(distribution, for_py_version, wheel, app_data):
    cmd = [
        sys.executable,
        "-c",
        "from virtualenv.seed.embed.wheels.periodic_update import do_update;"
        "do_update({!r}, {!r}, {!r}, {!r})".format(distribution, for_py_version, str(wheel.path), str(app_data.path)),
    ]
    kwargs = {"stdout": subprocess.PIPE, "stderr": subprocess.PIPE}
    if sys.platform == "win32":
        kwargs["creation_flags"] = DETACHED_PROCESS
    process = Popen(cmd, **kwargs)
    logging.info(
        "triggered periodic upgrade of %s==%s (for python %s) via background process having PID %d",
        distribution,
        wheel.version,
        for_py_version,
        process.pid,
    )
    process.communicate()  # on purpose not called to make it detached


def do_update(distribution, for_py_version, wheel_filename, app_data):
    temp_dir = Path(tempfile.mkdtemp())
    try:
        copy2(wheel_filename, temp_dir)
        local_wheel = Wheel(Path(wheel_filename))
        from .acquire import download_wheel

        with update_log_for_distribution(local_wheel.path.parent.parent, distribution) as u_log:

            download_wheel(distribution, None, for_py_version, temp_dir, ReentrantFileLock(app_data))

            new_wheels = [f for f in temp_dir.iterdir() if f.name != local_wheel.name]
            if new_wheels:
                new_wheel = new_wheels[0]
                dest = local_wheel.path.parent / new_wheel.name
                if not dest.exists():
                    copy2(new_wheel, dest)
            else:
                dest = local_wheel.path
            release_date = _get_release_date(dest)
            if u_log.updated is not None:
                u_log.previous_updated = u_log.updated
                u_log.previous_updated_release_date = u_log.updated_release_date
            u_log.updated = dest.name
            u_log.updated_release_date = release_date
            u_log.completed = datetime.now()
            u_log.update()

    finally:
        safe_delete(temp_dir)


def _get_release_date(dest):
    wheel = Wheel(dest)
    # the most accurate is to ask PyPi - https://pypi.org/pypi/pip/json
    try:
        with urlopen("https://pypi.org/pypi/{}/json".format(wheel.distribution)) as file_handler:
            content = json.load(file_handler)
        return datetime.strptime(content["releases"][wheel.version][0]["upload_time"], "%Y-%m-%dT%H:%M:%S")
    except Exception:  # noqa
        pass
    # otherwise can approximate from the version number https://pip.pypa.io/en/latest/development/release-process/
    released = datetime(year=2000 + wheel.version_tuple[0], month=wheel.version_tuple[1] * 3 + 1, day=1)
    released += timedelta(days=calendar.monthrange(released.year, released.month)[1])
    return released


__all__ = (
    "periodic_update",
    "do_update",
)
