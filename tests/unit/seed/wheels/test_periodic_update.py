from __future__ import absolute_import, unicode_literals

import subprocess
import sys
from datetime import datetime, timedelta

import pytest
from six.moves import zip_longest

from virtualenv import cli_run
from virtualenv.seed.wheels.embed import BUNDLE_SUPPORT, get_embed_wheel
from virtualenv.seed.wheels.periodic_update import (
    NewVersion,
    UpdateLog,
    load_datetime,
    manual_upgrade,
    periodic_update,
    trigger_update,
)
from virtualenv.util.subprocess import DETACHED_PROCESS


def test_manual_upgrade(session_app_data, caplog, mocker, for_py_version):
    wheel = get_embed_wheel("pip", for_py_version)
    new_version = NewVersion(wheel.path, datetime.now(), datetime.now() - timedelta(days=20))

    def _do_update(distribution, for_py_version, embed_filename, app_data, search_dirs, periodic):  # noqa
        if distribution == "pip":
            return [new_version]
        return []

    do_update = mocker.patch("virtualenv.seed.wheels.periodic_update.do_update", side_effect=_do_update)
    manual_upgrade(session_app_data)

    assert "upgrade pip" in caplog.text
    assert "upgraded pip" in caplog.text
    assert " new entries found:\n\tNewVersion" in caplog.text
    assert " no new versions found" in caplog.text
    assert do_update.call_count == 3 * len(BUNDLE_SUPPORT)


def test_pick_periodic_update(tmp_path, session_app_data, mocker, for_py_version):
    embed, current = get_embed_wheel("setuptools", "3.4"), get_embed_wheel("setuptools", for_py_version)
    mocker.patch("virtualenv.seed.wheels.bundle.load_embed_wheel", return_value=embed)
    completed = datetime.now() - timedelta(days=29)
    u_log = UpdateLog(
        started=datetime.now() - timedelta(days=30),
        completed=completed,
        versions=[NewVersion(filename=current.path, found_date=completed, release_date=completed)],
        periodic=True,
    )
    read_dict = mocker.patch("virtualenv.app_data.via_disk_folder.JSONStoreDisk.read", return_value=u_log.to_dict())

    result = cli_run([str(tmp_path), "--activators", "", "--no-periodic-update", "--no-wheel", "--no-pip"])

    assert read_dict.call_count == 1
    installed = list(i.name for i in result.creator.purelib.iterdir() if i.suffix == ".dist-info")
    assert "setuptools-{}.dist-info".format(current.version) in installed


def test_periodic_update_stops_at_current(mocker, session_app_data, for_py_version):
    current = get_embed_wheel("setuptools", for_py_version)

    now, completed = datetime.now(), datetime.now() - timedelta(days=29)
    u_log = UpdateLog(
        started=completed,
        completed=completed,
        versions=[
            NewVersion(wheel_path(current, (1,)), completed, now - timedelta(days=1)),
            NewVersion(filename=current.path, found_date=completed, release_date=now - timedelta(days=2)),
            NewVersion(wheel_path(current, (-1,)), completed, now - timedelta(days=30)),
        ],
        periodic=True,
    )
    mocker.patch("virtualenv.app_data.via_disk_folder.JSONStoreDisk.read", return_value=u_log.to_dict())

    result = periodic_update("setuptools", for_py_version, current, [], session_app_data, False)
    assert result.path == current.path


def test_periodic_update_latest_per_patch(mocker, session_app_data, for_py_version):
    current = get_embed_wheel("setuptools", for_py_version)
    now, completed = datetime.now(), datetime.now() - timedelta(days=29)
    u_log = UpdateLog(
        started=completed,
        completed=completed,
        versions=[
            NewVersion(wheel_path(current, (0, 1, 2)), completed, now - timedelta(days=1)),
            NewVersion(wheel_path(current, (0, 1, 1)), completed, now - timedelta(days=30)),
            NewVersion(filename=str(current.path), found_date=completed, release_date=now - timedelta(days=2)),
        ],
        periodic=True,
    )
    mocker.patch("virtualenv.app_data.via_disk_folder.JSONStoreDisk.read", return_value=u_log.to_dict())

    result = periodic_update("setuptools", for_py_version, current, [], session_app_data, False)
    assert result.path == current.path


def wheel_path(wheel, of):
    new_version = ".".join(str(i) for i in (tuple(sum(x) for x in zip_longest(wheel.version_tuple, of, fillvalue=0))))
    new_name = wheel.name.replace(wheel.version, new_version)
    return str(wheel.path.parent / new_name)


_UP_NOW = datetime.now()
_UPDATE_SKIP = {
    "started_just_now_no_complete": UpdateLog(started=_UP_NOW, completed=None, versions=[], periodic=True),
    "started_1_hour_no_complete": UpdateLog(
        started=_UP_NOW - timedelta(hours=1), completed=None, versions=[], periodic=True,
    ),
    "completed_under_two_weeks": UpdateLog(
        started=None, completed=_UP_NOW - timedelta(days=14), versions=[], periodic=True,
    ),
    "started_just_now_completed_two_weeks": UpdateLog(
        started=_UP_NOW, completed=_UP_NOW - timedelta(days=14, seconds=1), versions=[], periodic=True,
    ),
    "started_1_hour_completed_two_weeks": UpdateLog(
        started=_UP_NOW - timedelta(hours=1),
        completed=_UP_NOW - timedelta(days=14, seconds=1),
        versions=[],
        periodic=True,
    ),
}


@pytest.mark.parametrize("u_log", _UPDATE_SKIP.values(), ids=_UPDATE_SKIP.keys())
def test_periodic_update_skip(u_log, mocker, for_py_version, session_app_data, freezer):
    freezer.move_to(_UP_NOW)
    mocker.patch("virtualenv.app_data.via_disk_folder.JSONStoreDisk.read", return_value=u_log.to_dict())
    mocker.patch("virtualenv.seed.wheels.periodic_update.trigger_update", side_effect=RuntimeError)

    result = periodic_update("setuptools", for_py_version, None, [], session_app_data, True)
    assert result is None


_UPDATE_YES = {
    "never_started": UpdateLog(started=None, completed=None, versions=[], periodic=False),
    "started_1_hour": UpdateLog(
        started=_UP_NOW - timedelta(hours=1, microseconds=1), completed=None, versions=[], periodic=False,
    ),
    "completed_two_week": UpdateLog(
        started=_UP_NOW - timedelta(days=14, microseconds=2),
        completed=_UP_NOW - timedelta(days=14, microseconds=1),
        versions=[],
        periodic=False,
    ),
}


@pytest.mark.parametrize("u_log", _UPDATE_YES.values(), ids=_UPDATE_YES.keys())
def test_periodic_update_trigger(u_log, mocker, for_py_version, session_app_data, freezer):
    freezer.move_to(_UP_NOW)
    mocker.patch("virtualenv.app_data.via_disk_folder.JSONStoreDisk.read", return_value=u_log.to_dict())
    write = mocker.patch("virtualenv.app_data.via_disk_folder.JSONStoreDisk.write")
    trigger_update_ = mocker.patch("virtualenv.seed.wheels.periodic_update.trigger_update")

    result = periodic_update("setuptools", for_py_version, None, [], session_app_data, True)

    assert result is None
    assert trigger_update_.call_count
    assert write.call_count == 1
    wrote_json = write.call_args[0][0]
    assert wrote_json["periodic"] is True
    assert load_datetime(wrote_json["started"]) == _UP_NOW


def test_trigger_update_no_debug(for_py_version, session_app_data, tmp_path, mocker, monkeypatch):
    monkeypatch.delenv(str("_VIRTUALENV_PERIODIC_UPDATE_INLINE"), raising=False)
    current = get_embed_wheel("setuptools", for_py_version)
    process = mocker.MagicMock()
    process.communicate.return_value = None, None
    Popen = mocker.patch("virtualenv.seed.wheels.periodic_update.Popen", return_value=process)

    trigger_update("setuptools", for_py_version, current, [tmp_path / "a", tmp_path / "b"], session_app_data, True)

    assert Popen.call_count == 1
    args, kwargs = Popen.call_args
    assert args == (
        [
            sys.executable,
            "-c",
            "from virtualenv.seed.wheels.periodic_update import do_update;"
            "do_update('setuptools', '{}', '{}', '{}', ['{}', '{}'], True)".format(
                for_py_version, current.path, session_app_data, tmp_path / "a", tmp_path / "b",
            ),
        ],
    )
    expected = {"stdout": subprocess.PIPE, "stderr": subprocess.PIPE}
    if sys.platform == "win32":
        expected["creationflags"] = DETACHED_PROCESS
    assert kwargs == expected
    assert process.communicate.call_count == 0


def test_trigger_update_debug(for_py_version, session_app_data, tmp_path, mocker, monkeypatch):
    monkeypatch.setenv(str("_VIRTUALENV_PERIODIC_UPDATE_INLINE"), str("1"))
    current = get_embed_wheel("pip", for_py_version)

    process = mocker.MagicMock()
    process.communicate.return_value = None, None
    Popen = mocker.patch("virtualenv.seed.wheels.periodic_update.Popen", return_value=process)

    trigger_update("pip", for_py_version, current, [tmp_path / "a", tmp_path / "b"], session_app_data, False)

    assert Popen.call_count == 1
    args, kwargs = Popen.call_args
    assert args == (
        [
            sys.executable,
            "-c",
            "from virtualenv.seed.wheels.periodic_update import do_update;"
            "do_update('pip', '{}', '{}', '{}', ['{}', '{}'], False)".format(
                for_py_version, current.path, session_app_data, tmp_path / "a", tmp_path / "b",
            ),
        ],
    )
    expected = {"stdout": None, "stderr": None}
    if sys.platform == "win32":
        expected["creationflags"] = DETACHED_PROCESS
    assert kwargs == expected
    assert process.communicate.call_count == 1
