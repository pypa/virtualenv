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
    for filename, release_date in (
        (update_log.updated, update_log.updated_release_date),
        (update_log.previous_updated, update_log.previous_updated_release_date),
    ):
        if filename is None or filename == wheel.name:
            continue
        updated_wheel = Wheel(cache_dir / filename)
        # use it only if released long enough time ago - use version number to approximate release
        # only use if it has been released for at least 28 days
        if datetime.now() - release_date > timedelta(days=28):
            logging.debug("using periodically updated wheel %s", updated_wheel)
            return updated_wheel
    return wheel


@contextmanager
def update_log_for_distribution(folder, distribution, no_block=False):
    root_lock, lock_name = ReentrantFileLock(folder), "{}.update.lock".format(distribution)
    try:
        with root_lock.lock_for_key(lock_name, no_block=no_block):
            update_log = UpdateLog(folder / "{}.update.json".format(distribution))
            yield update_log
    except Timeout:
        return


class UpdateLog(object):
    datetime_fmt = "%Y-%m-%dT%H:%M:%SZ"

    def __init__(self, path):
        content = {}
        if path.exists():
            try:
                with open(str(path), "rt") as file_handler:
                    content = json.load(file_handler)
            except (IOError, ValueError):
                pass
        self.started = self._load_datetime(content, "started")
        self.completed = self._load_datetime(content, "completed")

        self.updated = content.get("updated")
        self.updated_release_date = content.get("updated_release_date")

        self.previous_updated = content.get("previous_updated")
        self.previous_updated_release_date = content.get("previous_updated_release_date")
        self.path = path

    def _load_datetime(self, content, key):
        value = content.get(key)
        if value:
            return datetime.strptime(value, self.datetime_fmt)
        return None

    def _dump_datetime(self, value):
        if value is None:
            return None
        return datetime.strftime(value, self.datetime_fmt)

    @property
    def needs_update(self):
        now = datetime.now()
        if self.completed is None:  # never completed
            return self._check_start(now)
        else:
            delta_since_last_completed = now - self.completed
            if delta_since_last_completed < timedelta(days=13):
                return False
            return self._check_start(now)

    def _check_start(self, now):
        if self.started is None:  # never started
            return True
        delta_since_last_start = now - self.started
        if delta_since_last_start >= timedelta(hours=1):  # over an hour ago -> operations crashed, try again
            return True
        return False

    def update(self):
        content = {
            "started": self._dump_datetime(self.started),
            "completed": self._dump_datetime(self.completed),
            "updated": self.updated,
            "updated_release_date": self._dump_datetime(self.updated_release_date),
            "previous_updated": self.previous_updated,
            "previous_updated_release_date": self._dump_datetime(self.previous_updated_release_date),
        }
        with open(str(self.path), "wt") as file_handler:
            json.dump(content, file_handler, sort_keys=True, indent=4)


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
    # process.communicate()


def do_update(distribution, for_py_version, wheel_filename, app_data):
    temp_dir = Path(tempfile.mkdtemp())
    try:
        copy2(wheel_filename, temp_dir)
        from .acquire import download_wheel

        download_wheel(distribution, None, for_py_version, temp_dir, ReentrantFileLock(app_data))
        local_wheel = Path(wheel_filename)
        new_wheels = [f for f in temp_dir.iterdir() if f.name != local_wheel.name]
        if new_wheels:
            new_wheel = new_wheels[0]
            dest = local_wheel.parent / new_wheel.name
            if not dest.exists():
                copy2(new_wheel, dest)
        else:
            dest = local_wheel
        release_date = _get_release_date(dest)
        with update_log_for_distribution(local_wheel.parent.parent, distribution, no_block=False) as u_log:
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
