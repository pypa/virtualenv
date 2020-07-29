from __future__ import absolute_import, unicode_literals

import json
import subprocess
import sys
from collections import defaultdict
from contextlib import contextmanager
from datetime import datetime, timedelta
from textwrap import dedent

import pytest
from six import StringIO
from six.moves import zip_longest
from six.moves.urllib.error import URLError

from virtualenv import cli_run
from virtualenv.app_data import AppDataDiskFolder
from virtualenv.seed.wheels import Wheel
from virtualenv.seed.wheels.embed import BUNDLE_SUPPORT, get_embed_wheel
from virtualenv.seed.wheels.periodic_update import (
    NewVersion,
    UpdateLog,
    do_update,
    dump_datetime,
    load_datetime,
    manual_upgrade,
    periodic_update,
    release_date_for_wheel_path,
    trigger_update,
)
from virtualenv.util.path import Path
from virtualenv.util.subprocess import DETACHED_PROCESS


@pytest.fixture(autouse=True)
def clear_pypi_info_cache():
    from virtualenv.seed.wheels.periodic_update import _PYPI_CACHE

    _PYPI_CACHE.clear()


def test_manual_upgrade(session_app_data, caplog, mocker, for_py_version):
    wheel = get_embed_wheel("pip", for_py_version)
    new_version = NewVersion(wheel.path, datetime.now(), datetime.now() - timedelta(days=20))

    def _do_update(distribution, for_py_version, embed_filename, app_data, search_dirs, periodic):  # noqa
        if distribution == "pip":
            return [new_version]
        return []

    do_update_mock = mocker.patch("virtualenv.seed.wheels.periodic_update.do_update", side_effect=_do_update)
    manual_upgrade(session_app_data)

    assert "upgrade pip" in caplog.text
    assert "upgraded pip" in caplog.text
    assert " new entries found:\n\tNewVersion" in caplog.text
    assert " no new versions found" in caplog.text
    packages = defaultdict(list)
    for i in do_update_mock.call_args_list:
        packages[i[1]["distribution"]].append(i[1]["for_py_version"])
    packages = {key: sorted(value) for key, value in packages.items()}
    versions = list(sorted(BUNDLE_SUPPORT.keys()))
    expected = {"setuptools": versions, "wheel": versions, "pip": versions}
    assert packages == expected


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


@pytest.mark.parametrize("u_log", list(_UPDATE_SKIP.values()), ids=list(_UPDATE_SKIP.keys()))
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


@pytest.mark.parametrize("u_log", list(_UPDATE_YES.values()), ids=list(_UPDATE_YES.keys()))
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
    cmd = (
        dedent(
            """
        from virtualenv.report import setup_report, MAX_LEVEL
        from virtualenv.seed.wheels.periodic_update import do_update
        setup_report(MAX_LEVEL, show_pid=True)
        do_update({!r}, {!r}, {!r}, {!r}, {!r}, {!r})
        """,
        )
        .strip()
        .format(
            "setuptools",
            for_py_version,
            str(current.path),
            str(session_app_data),
            [str(tmp_path / "a"), str(tmp_path / "b")],
            True,
        )
    )

    assert args == ([sys.executable, "-c", cmd],)
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
    cmd = (
        dedent(
            """
        from virtualenv.report import setup_report, MAX_LEVEL
        from virtualenv.seed.wheels.periodic_update import do_update
        setup_report(MAX_LEVEL, show_pid=True)
        do_update({!r}, {!r}, {!r}, {!r}, {!r}, {!r})
        """,
        )
        .strip()
        .format(
            "pip",
            for_py_version,
            str(current.path),
            str(session_app_data),
            [str(tmp_path / "a"), str(tmp_path / "b")],
            False,
        )
    )
    assert args == ([sys.executable, "-c", cmd],)
    expected = {"stdout": None, "stderr": None}
    assert kwargs == expected
    assert process.communicate.call_count == 1


def test_do_update_first(tmp_path, mocker, freezer):
    freezer.move_to(_UP_NOW)
    wheel = get_embed_wheel("pip", "3.9")
    app_data_outer = AppDataDiskFolder(str(tmp_path / "app"))
    extra = tmp_path / "extra"
    extra.mkdir()

    pip_version_remote = [
        (wheel_path(wheel, (1, 0, 0)), None),
        (wheel_path(wheel, (0, 1, 0)), _UP_NOW - timedelta(days=1)),
        (wheel_path(wheel, (0, 0, 1)), _UP_NOW - timedelta(days=2)),
        (wheel.path, _UP_NOW - timedelta(days=3)),
        (wheel_path(wheel, (-1, 0, 0)), _UP_NOW - timedelta(days=30)),
    ]
    download_wheels = (Wheel(Path(i[0])) for i in pip_version_remote)

    def _download_wheel(distribution, version_spec, for_py_version, search_dirs, app_data, to_folder):
        assert distribution == "pip"
        assert for_py_version == "3.9"
        assert [str(i) for i in search_dirs] == [str(extra)]
        assert isinstance(app_data, AppDataDiskFolder)
        assert to_folder == app_data_outer.house
        return next(download_wheels)

    download_wheel = mocker.patch("virtualenv.seed.wheels.acquire.download_wheel", side_effect=_download_wheel)
    releases = {
        Wheel(Path(wheel)).version: [
            {"upload_time": datetime.strftime(release_date, "%Y-%m-%dT%H:%M:%S") if release_date is not None else None},
        ]
        for wheel, release_date in pip_version_remote
    }
    pypi_release = json.dumps({"releases": releases})

    @contextmanager
    def _release(of, context):
        assert of == "https://pypi.org/pypi/pip/json"
        assert context is None
        yield StringIO(pypi_release)

    url_o = mocker.patch("virtualenv.seed.wheels.periodic_update.urlopen", side_effect=_release)

    last_update = _UP_NOW - timedelta(days=14)
    u_log = UpdateLog(started=last_update, completed=last_update, versions=[], periodic=True)
    read_dict = mocker.patch("virtualenv.app_data.via_disk_folder.JSONStoreDisk.read", return_value=u_log.to_dict())
    write = mocker.patch("virtualenv.app_data.via_disk_folder.JSONStoreDisk.write")
    copy = mocker.patch("virtualenv.seed.wheels.periodic_update.copy2")

    versions = do_update("pip", "3.9", str(pip_version_remote[-1][0]), str(app_data_outer), [str(extra)], True)

    assert download_wheel.call_count == len(pip_version_remote)
    assert url_o.call_count == 1
    assert copy.call_count == 1

    expected = [
        NewVersion(Path(wheel).name, _UP_NOW, None if release is None else release.replace(microsecond=0))
        for wheel, release in pip_version_remote
    ]
    assert versions == expected

    assert read_dict.call_count == 1
    assert write.call_count == 1
    wrote_json = write.call_args[0][0]
    assert wrote_json == {
        "started": dump_datetime(last_update),
        "completed": dump_datetime(_UP_NOW),
        "periodic": True,
        "versions": [e.to_dict() for e in expected],
    }


def test_do_update_skip_already_done(tmp_path, mocker, freezer):
    freezer.move_to(_UP_NOW + timedelta(hours=1))
    wheel = get_embed_wheel("pip", "3.9")
    app_data_outer = AppDataDiskFolder(str(tmp_path / "app"))
    extra = tmp_path / "extra"
    extra.mkdir()

    def _download_wheel(distribution, version_spec, for_py_version, search_dirs, app_data, to_folder):  # noqa
        return wheel.path

    download_wheel = mocker.patch("virtualenv.seed.wheels.acquire.download_wheel", side_effect=_download_wheel)
    url_o = mocker.patch("virtualenv.seed.wheels.periodic_update.urlopen", side_effect=RuntimeError)

    released = _UP_NOW - timedelta(days=30)
    u_log = UpdateLog(
        started=_UP_NOW - timedelta(days=31),
        completed=released,
        versions=[NewVersion(filename=wheel.path.name, found_date=released, release_date=released)],
        periodic=True,
    )
    read_dict = mocker.patch("virtualenv.app_data.via_disk_folder.JSONStoreDisk.read", return_value=u_log.to_dict())
    write = mocker.patch("virtualenv.app_data.via_disk_folder.JSONStoreDisk.write")

    versions = do_update("pip", "3.9", str(wheel.path), str(app_data_outer), [str(extra)], False)

    assert download_wheel.call_count == 1
    assert read_dict.call_count == 1
    assert not url_o.call_count
    assert versions == []

    assert write.call_count == 1
    wrote_json = write.call_args[0][0]
    assert wrote_json == {
        "started": dump_datetime(_UP_NOW + timedelta(hours=1)),
        "completed": dump_datetime(_UP_NOW + timedelta(hours=1)),
        "periodic": False,
        "versions": [
            {
                "filename": wheel.path.name,
                "release_date": dump_datetime(released),
                "found_date": dump_datetime(released),
            },
        ],
    }


def test_new_version_eq():
    value = NewVersion("a", datetime.now(), datetime.now())
    assert value == value


def test_new_version_ne():
    assert NewVersion("a", datetime.now(), datetime.now()) != NewVersion(
        "a", datetime.now(), datetime.now() + timedelta(hours=1),
    )


def test_get_release_unsecure(mocker, caplog):
    @contextmanager
    def _release(of, context):
        assert of == "https://pypi.org/pypi/pip/json"
        if context is None:
            raise URLError("insecure")
        assert context
        yield StringIO(json.dumps({"releases": {"20.1": [{"upload_time": "2020-12-22T12:12:12"}]}}))

    url_o = mocker.patch("virtualenv.seed.wheels.periodic_update.urlopen", side_effect=_release)

    result = release_date_for_wheel_path(Path("pip-20.1.whl"))

    assert result == datetime(year=2020, month=12, day=22, hour=12, minute=12, second=12)
    assert url_o.call_count == 2
    assert "insecure" in caplog.text
    assert " failed " in caplog.text


def test_get_release_fails(mocker, caplog):
    exc = RuntimeError("oh no")
    url_o = mocker.patch("virtualenv.seed.wheels.periodic_update.urlopen", side_effect=exc)

    result = release_date_for_wheel_path(Path("pip-20.1.whl"))

    assert result is None
    assert url_o.call_count == 1
    assert repr(exc) in caplog.text


def test_download_stop_with_embed(tmp_path, mocker, freezer):
    freezer.move_to(_UP_NOW)
    wheel = get_embed_wheel("pip", "3.9")
    app_data_outer = AppDataDiskFolder(str(tmp_path / "app"))
    pip_version_remote = [wheel_path(wheel, (0, 0, 2)), wheel_path(wheel, (0, 0, 1)), wheel_path(wheel, (-1, 0, 0))]
    at = {"index": 0}

    def download():
        while True:
            path = pip_version_remote[at["index"]]
            at["index"] += 1
            yield Wheel(Path(path))

    do = download()
    download_wheel = mocker.patch("virtualenv.seed.wheels.acquire.download_wheel", side_effect=lambda *a, **k: next(do))
    url_o = mocker.patch("virtualenv.seed.wheels.periodic_update.urlopen", side_effect=URLError("unavailable"))

    last_update = _UP_NOW - timedelta(days=14)
    u_log = UpdateLog(started=last_update, completed=last_update, versions=[], periodic=True)
    read_dict = mocker.patch("virtualenv.app_data.via_disk_folder.JSONStoreDisk.read", return_value=u_log.to_dict())
    write = mocker.patch("virtualenv.app_data.via_disk_folder.JSONStoreDisk.write")

    do_update("pip", "3.9", str(wheel.path), str(app_data_outer), [], True)

    assert download_wheel.call_count == 3
    assert url_o.call_count == 2

    assert read_dict.call_count == 1
    assert write.call_count == 1
