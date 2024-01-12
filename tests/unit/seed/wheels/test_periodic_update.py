from __future__ import annotations

import json
import os
import subprocess
import sys
from collections import defaultdict
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from io import StringIO
from itertools import zip_longest
from pathlib import Path
from textwrap import dedent
from urllib.error import URLError

import pytest

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
from virtualenv.util.subprocess import CREATE_NO_WINDOW


@pytest.fixture(autouse=True)
def _clear_pypi_info_cache():
    from virtualenv.seed.wheels.periodic_update import _PYPI_CACHE  # noqa: PLC0415

    _PYPI_CACHE.clear()


def test_manual_upgrade(session_app_data, caplog, mocker, for_py_version):
    wheel = get_embed_wheel("pip", for_py_version)
    new_version = NewVersion(
        wheel.path,
        datetime.now(tz=timezone.utc),
        datetime.now(tz=timezone.utc) - timedelta(days=20),
        "manual",
    )

    def _do_update(  # noqa: PLR0913
        distribution,
        for_py_version,  # noqa: ARG001
        embed_filename,  # noqa: ARG001
        app_data,  # noqa: ARG001
        search_dirs,  # noqa: ARG001
        periodic,  # noqa: ARG001
    ):
        if distribution == "pip":
            return [new_version]
        return []

    do_update_mock = mocker.patch("virtualenv.seed.wheels.periodic_update.do_update", side_effect=_do_update)
    manual_upgrade(session_app_data, os.environ)

    assert "upgrade pip" in caplog.text
    assert "upgraded pip" in caplog.text
    assert " no new versions found" in caplog.text
    assert " new entries found:\n" in caplog.text
    assert "\tNewVersion(" in caplog.text
    packages = defaultdict(list)
    for args in do_update_mock.call_args_list:
        packages[args[1]["distribution"]].append(args[1]["for_py_version"])
    packages = {key: sorted(value) for key, value in packages.items()}
    versions = sorted(BUNDLE_SUPPORT.keys())
    expected = {"setuptools": versions, "wheel": versions, "pip": versions}
    assert packages == expected


@pytest.mark.usefixtures("session_app_data")
def test_pick_periodic_update(tmp_path, mocker, for_py_version):
    embed, current = get_embed_wheel("setuptools", "3.6"), get_embed_wheel("setuptools", for_py_version)
    mocker.patch("virtualenv.seed.wheels.bundle.load_embed_wheel", return_value=embed)
    completed = datetime.now(tz=timezone.utc) - timedelta(days=29)
    u_log = UpdateLog(
        started=datetime.now(tz=timezone.utc) - timedelta(days=30),
        completed=completed,
        versions=[NewVersion(filename=current.path, found_date=completed, release_date=completed, source="periodic")],
        periodic=True,
    )
    read_dict = mocker.patch("virtualenv.app_data.via_disk_folder.JSONStoreDisk.read", return_value=u_log.to_dict())

    result = cli_run(
        [
            str(tmp_path),
            "--activators",
            "",
            "--no-periodic-update",
            "--no-wheel",
            "--no-pip",
            "--setuptools",
            "bundle",
            "--wheel",
            "bundle",
        ],
    )

    assert read_dict.call_count == 1
    installed = [i.name for i in result.creator.purelib.iterdir() if i.suffix == ".dist-info"]
    assert f"setuptools-{current.version}.dist-info" in installed


def test_periodic_update_stops_at_current(mocker, session_app_data, for_py_version):
    current = get_embed_wheel("setuptools", for_py_version)

    now, completed = datetime.now(tz=timezone.utc), datetime.now(tz=timezone.utc) - timedelta(days=29)
    u_log = UpdateLog(
        started=completed,
        completed=completed,
        versions=[
            NewVersion(wheel_path(current, (1,)), completed, now - timedelta(days=1), "periodic"),
            NewVersion(current.path, completed, now - timedelta(days=2), "periodic"),
            NewVersion(wheel_path(current, (-1,)), completed, now - timedelta(days=30), "periodic"),
        ],
        periodic=True,
    )
    mocker.patch("virtualenv.app_data.via_disk_folder.JSONStoreDisk.read", return_value=u_log.to_dict())

    result = periodic_update("setuptools", None, for_py_version, current, [], session_app_data, False, os.environ)
    assert result.path == current.path


def test_periodic_update_latest_per_patch(mocker, session_app_data, for_py_version):
    current = get_embed_wheel("setuptools", for_py_version)
    expected_path = wheel_path(current, (0, 1, 2))
    now = datetime.now(tz=timezone.utc)
    completed = now - timedelta(hours=2)
    u_log = UpdateLog(
        started=completed,
        completed=completed,
        periodic=True,
        versions=[
            NewVersion(expected_path, completed, now - timedelta(days=1), "periodic"),
            NewVersion(wheel_path(current, (0, 1, 1)), completed, now - timedelta(days=30), "periodic"),
            NewVersion(str(current.path), completed, now - timedelta(days=31), "periodic"),
        ],
    )
    mocker.patch("virtualenv.app_data.via_disk_folder.JSONStoreDisk.read", return_value=u_log.to_dict())

    result = periodic_update("setuptools", None, for_py_version, current, [], session_app_data, False, os.environ)
    assert str(result.path) == expected_path


def test_periodic_update_latest_per_patch_prev_is_manual(mocker, session_app_data, for_py_version):
    current = get_embed_wheel("setuptools", for_py_version)
    expected_path = wheel_path(current, (0, 1, 2))
    now = datetime.now(tz=timezone.utc)
    completed = now - timedelta(hours=2)
    u_log = UpdateLog(
        started=completed,
        completed=completed,
        periodic=True,
        versions=[
            NewVersion(expected_path, completed, completed, "periodic"),
            NewVersion(wheel_path(current, (0, 1, 1)), completed, now - timedelta(days=10), "manual"),
            NewVersion(wheel_path(current, (0, 1, 0)), completed, now - timedelta(days=11), "periodic"),
            NewVersion(str(current.path), completed, now - timedelta(days=12), "manual"),
        ],
    )
    mocker.patch("virtualenv.app_data.via_disk_folder.JSONStoreDisk.read", return_value=u_log.to_dict())

    result = periodic_update("setuptools", None, for_py_version, current, [], session_app_data, False, os.environ)
    assert str(result.path) == expected_path


def test_manual_update_honored(mocker, session_app_data, for_py_version):
    current = get_embed_wheel("setuptools", for_py_version)
    expected_path = wheel_path(current, (0, 1, 1))
    now = datetime.now(tz=timezone.utc)
    completed = now
    u_log = UpdateLog(
        started=completed,
        completed=completed,
        periodic=True,
        versions=[
            NewVersion(wheel_path(current, (0, 1, 2)), completed, completed, "periodic"),
            NewVersion(expected_path, completed, now - timedelta(days=10), "manual"),
            NewVersion(wheel_path(current, (0, 1, 0)), completed, now - timedelta(days=11), "periodic"),
            NewVersion(str(current.path), completed, now - timedelta(days=12), "manual"),
        ],
    )
    mocker.patch("virtualenv.app_data.via_disk_folder.JSONStoreDisk.read", return_value=u_log.to_dict())

    result = periodic_update("setuptools", None, for_py_version, current, [], session_app_data, False, os.environ)
    assert str(result.path) == expected_path


def wheel_path(wheel, of, pre_release=""):
    new_version = ".".join(str(i) for i in (tuple(sum(x) for x in zip_longest(wheel.version_tuple, of, fillvalue=0))))
    new_name = wheel.name.replace(wheel.version, new_version + pre_release)
    return str(wheel.path.parent / new_name)


_UP_NOW = datetime.now(tz=timezone.utc)
_UPDATE_SKIP = {
    "started_just_now_no_complete": UpdateLog(started=_UP_NOW, completed=None, versions=[], periodic=True),
    "started_1_hour_no_complete": UpdateLog(
        started=_UP_NOW - timedelta(hours=1),
        completed=None,
        versions=[],
        periodic=True,
    ),
    "completed_under_two_weeks": UpdateLog(
        started=None,
        completed=_UP_NOW - timedelta(days=14),
        versions=[],
        periodic=True,
    ),
    "started_just_now_completed_two_weeks": UpdateLog(
        started=_UP_NOW,
        completed=_UP_NOW - timedelta(days=14, seconds=1),
        versions=[],
        periodic=True,
    ),
    "started_1_hour_completed_two_weeks": UpdateLog(
        started=_UP_NOW - timedelta(hours=1),
        completed=_UP_NOW - timedelta(days=14, seconds=1),
        versions=[],
        periodic=True,
    ),
}


@pytest.mark.parametrize("u_log", list(_UPDATE_SKIP.values()), ids=list(_UPDATE_SKIP.keys()))
def test_periodic_update_skip(u_log, mocker, for_py_version, session_app_data, time_freeze):
    time_freeze(_UP_NOW)
    mocker.patch("virtualenv.app_data.via_disk_folder.JSONStoreDisk.read", return_value=u_log.to_dict())
    mocker.patch("virtualenv.seed.wheels.periodic_update.trigger_update", side_effect=RuntimeError)

    result = periodic_update("setuptools", None, for_py_version, None, [], session_app_data, os.environ, True)
    assert result is None


_UPDATE_YES = {
    "never_started": UpdateLog(started=None, completed=None, versions=[], periodic=False),
    "started_1_hour": UpdateLog(
        started=_UP_NOW - timedelta(hours=1, microseconds=1),
        completed=None,
        versions=[],
        periodic=False,
    ),
    "completed_two_week": UpdateLog(
        started=_UP_NOW - timedelta(days=14, microseconds=2),
        completed=_UP_NOW - timedelta(days=14, microseconds=1),
        versions=[],
        periodic=False,
    ),
}


@pytest.mark.parametrize("u_log", list(_UPDATE_YES.values()), ids=list(_UPDATE_YES.keys()))
def test_periodic_update_trigger(u_log, mocker, for_py_version, session_app_data, time_freeze):
    time_freeze(_UP_NOW)
    mocker.patch("virtualenv.app_data.via_disk_folder.JSONStoreDisk.read", return_value=u_log.to_dict())
    write = mocker.patch("virtualenv.app_data.via_disk_folder.JSONStoreDisk.write")
    trigger_update_ = mocker.patch("virtualenv.seed.wheels.periodic_update.trigger_update")

    result = periodic_update("setuptools", None, for_py_version, None, [], session_app_data, os.environ, True)

    assert result is None
    assert trigger_update_.call_count
    assert write.call_count == 1
    wrote_json = write.call_args[0][0]
    assert wrote_json["periodic"] is True
    assert load_datetime(wrote_json["started"]) == _UP_NOW


def test_trigger_update_no_debug(for_py_version, session_app_data, tmp_path, mocker, monkeypatch):
    monkeypatch.delenv("_VIRTUALENV_PERIODIC_UPDATE_INLINE", raising=False)
    current = get_embed_wheel("setuptools", for_py_version)
    process = mocker.MagicMock()
    process.communicate.return_value = None, None
    Popen = mocker.patch("virtualenv.seed.wheels.periodic_update.Popen", return_value=process)  # noqa: N806

    trigger_update(
        "setuptools",
        for_py_version,
        current,
        [tmp_path / "a", tmp_path / "b"],
        session_app_data,
        os.environ,
        True,
    )

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
    expected = {"stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
    if sys.platform == "win32":
        expected["creationflags"] = CREATE_NO_WINDOW
    assert kwargs == expected
    assert process.communicate.call_count == 0


def test_trigger_update_debug(for_py_version, session_app_data, tmp_path, mocker, monkeypatch):
    monkeypatch.setenv("_VIRTUALENV_PERIODIC_UPDATE_INLINE", "1")
    current = get_embed_wheel("pip", for_py_version)

    process = mocker.MagicMock()
    process.communicate.return_value = None, None
    Popen = mocker.patch("virtualenv.seed.wheels.periodic_update.Popen", return_value=process)  # noqa: N806

    trigger_update(
        "pip",
        for_py_version,
        current,
        [tmp_path / "a", tmp_path / "b"],
        session_app_data,
        os.environ,
        False,
    )

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


def test_do_update_first(tmp_path, mocker, time_freeze):
    time_freeze(_UP_NOW)
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

    def _download_wheel(  # noqa: PLR0913
        distribution,
        version_spec,  # noqa: ARG001
        for_py_version,
        search_dirs,
        app_data,
        to_folder,
        env,  # noqa: ARG001
    ):
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
        NewVersion(Path(wheel).name, _UP_NOW, None if release is None else release.replace(microsecond=0), "periodic")
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


def test_do_update_skip_already_done(tmp_path, mocker, time_freeze):
    time_freeze(_UP_NOW + timedelta(hours=1))
    wheel = get_embed_wheel("pip", "3.9")
    app_data_outer = AppDataDiskFolder(str(tmp_path / "app"))
    extra = tmp_path / "extra"
    extra.mkdir()

    def _download_wheel(  # noqa: PLR0913
        distribution,  # noqa: ARG001
        version_spec,  # noqa: ARG001
        for_py_version,  # noqa: ARG001
        search_dirs,  # noqa: ARG001
        app_data,  # noqa: ARG001
        to_folder,  # noqa: ARG001
        env,  # noqa: ARG001
    ):
        return wheel.path

    download_wheel = mocker.patch("virtualenv.seed.wheels.acquire.download_wheel", side_effect=_download_wheel)
    url_o = mocker.patch("virtualenv.seed.wheels.periodic_update.urlopen", side_effect=RuntimeError)

    released = _UP_NOW - timedelta(days=30)
    u_log = UpdateLog(
        started=_UP_NOW - timedelta(days=31),
        completed=released,
        versions=[NewVersion(filename=wheel.path.name, found_date=released, release_date=released, source="periodic")],
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
                "source": "manual",  # changed from "periodic" to "manual"
            },
        ],
    }


def test_new_version_eq():
    now = datetime.now(tz=timezone.utc)
    value = NewVersion("a", now, now, "periodic")
    assert value == NewVersion("a", now, now, "periodic")


def test_new_version_ne():
    assert NewVersion("a", datetime.now(tz=timezone.utc), datetime.now(tz=timezone.utc), "periodic") != NewVersion(
        "a",
        datetime.now(tz=timezone.utc),
        datetime.now(tz=timezone.utc) + timedelta(hours=1),
        "manual",
    )


def test_get_release_unsecure(mocker, caplog):
    @contextmanager
    def _release(of, context):
        assert of == "https://pypi.org/pypi/pip/json"
        if context is None:
            msg = "insecure"
            raise URLError(msg)
        assert context
        yield StringIO(json.dumps({"releases": {"20.1": [{"upload_time": "2020-12-22T12:12:12"}]}}))

    url_o = mocker.patch("virtualenv.seed.wheels.periodic_update.urlopen", side_effect=_release)

    result = release_date_for_wheel_path(Path("pip-20.1.whl"))

    assert result == datetime(year=2020, month=12, day=22, hour=12, minute=12, second=12, tzinfo=timezone.utc)
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


def mock_download(mocker, pip_version_remote):
    def download():
        index = 0
        while True:
            path = pip_version_remote[index]
            index += 1
            yield Wheel(Path(path))

    do = download()
    return mocker.patch(
        "virtualenv.seed.wheels.acquire.download_wheel",
        side_effect=lambda *a, **k: next(do),  # noqa: ARG005
    )


def test_download_stop_with_embed(tmp_path, mocker, time_freeze):
    time_freeze(_UP_NOW)
    wheel = get_embed_wheel("pip", "3.9")
    app_data_outer = AppDataDiskFolder(str(tmp_path / "app"))
    pip_version_remote = [wheel_path(wheel, (0, 0, 2)), wheel_path(wheel, (0, 0, 1)), wheel_path(wheel, (-1, 0, 0))]

    download_wheel = mock_download(mocker, pip_version_remote)
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


def test_download_manual_stop_after_one_download(tmp_path, mocker, time_freeze):
    time_freeze(_UP_NOW)
    wheel = get_embed_wheel("pip", "3.9")
    app_data_outer = AppDataDiskFolder(str(tmp_path / "app"))
    pip_version_remote = [wheel_path(wheel, (0, 1, 1))]

    download_wheel = mock_download(mocker, pip_version_remote)
    url_o = mocker.patch("virtualenv.seed.wheels.periodic_update.urlopen", side_effect=URLError("unavailable"))

    last_update = _UP_NOW - timedelta(days=14)
    u_log = UpdateLog(started=last_update, completed=last_update, versions=[], periodic=True)
    read_dict = mocker.patch("virtualenv.app_data.via_disk_folder.JSONStoreDisk.read", return_value=u_log.to_dict())
    write = mocker.patch("virtualenv.app_data.via_disk_folder.JSONStoreDisk.write")

    do_update("pip", "3.9", str(wheel.path), str(app_data_outer), [], False)

    assert download_wheel.call_count == 1
    assert url_o.call_count == 2
    assert read_dict.call_count == 1
    assert write.call_count == 1


def test_download_manual_ignores_pre_release(tmp_path, mocker, time_freeze):
    time_freeze(_UP_NOW)
    wheel = get_embed_wheel("pip", "3.9")
    app_data_outer = AppDataDiskFolder(str(tmp_path / "app"))
    pip_version_remote = [wheel_path(wheel, (0, 0, 1))]
    pip_version_pre = NewVersion(Path(wheel_path(wheel, (0, 1, 0), "b1")).name, _UP_NOW, None, "downloaded")

    download_wheel = mock_download(mocker, pip_version_remote)
    url_o = mocker.patch("virtualenv.seed.wheels.periodic_update.urlopen", side_effect=URLError("unavailable"))

    last_update = _UP_NOW - timedelta(days=14)
    u_log = UpdateLog(started=last_update, completed=last_update, versions=[pip_version_pre], periodic=True)
    read_dict = mocker.patch("virtualenv.app_data.via_disk_folder.JSONStoreDisk.read", return_value=u_log.to_dict())
    write = mocker.patch("virtualenv.app_data.via_disk_folder.JSONStoreDisk.write")

    do_update("pip", "3.9", str(wheel.path), str(app_data_outer), [], False)

    assert download_wheel.call_count == 1
    assert url_o.call_count == 2
    assert read_dict.call_count == 1
    assert write.call_count == 1
    wrote_json = write.call_args[0][0]
    assert wrote_json["versions"] == [
        {
            "filename": Path(pip_version_remote[0]).name,
            "release_date": None,
            "found_date": dump_datetime(_UP_NOW),
            "source": "manual",
        },
        pip_version_pre.to_dict(),
    ]


def test_download_periodic_stop_at_first_usable(tmp_path, mocker, time_freeze):
    time_freeze(_UP_NOW)
    wheel = get_embed_wheel("pip", "3.9")
    app_data_outer = AppDataDiskFolder(str(tmp_path / "app"))
    pip_version_remote = [wheel_path(wheel, (0, 1, 1)), wheel_path(wheel, (0, 1, 0))]
    rel_date_remote = [_UP_NOW - timedelta(days=1), _UP_NOW - timedelta(days=30)]

    download_wheel = mock_download(mocker, pip_version_remote)

    rel_date_gen = iter(rel_date_remote)
    release_date = mocker.patch(
        "virtualenv.seed.wheels.periodic_update.release_date_for_wheel_path",
        side_effect=lambda *a, **k: next(rel_date_gen),  # noqa: ARG005
    )

    last_update = _UP_NOW - timedelta(days=14)
    u_log = UpdateLog(started=last_update, completed=last_update, versions=[], periodic=True)
    read_dict = mocker.patch("virtualenv.app_data.via_disk_folder.JSONStoreDisk.read", return_value=u_log.to_dict())
    write = mocker.patch("virtualenv.app_data.via_disk_folder.JSONStoreDisk.write")

    do_update("pip", "3.9", str(wheel.path), str(app_data_outer), [], True)

    assert download_wheel.call_count == 2
    assert release_date.call_count == 2
    assert read_dict.call_count == 1
    assert write.call_count == 1


def test_download_periodic_stop_at_first_usable_with_previous_minor(tmp_path, mocker, time_freeze):
    time_freeze(_UP_NOW)
    wheel = get_embed_wheel("pip", "3.9")
    app_data_outer = AppDataDiskFolder(str(tmp_path / "app"))
    pip_version_remote = [wheel_path(wheel, (0, 1, 1)), wheel_path(wheel, (0, 1, 0)), wheel_path(wheel, (0, -1, 0))]
    rel_date_remote = [_UP_NOW - timedelta(days=1), _UP_NOW - timedelta(days=30), _UP_NOW - timedelta(days=40)]
    downloaded_versions = [
        NewVersion(Path(pip_version_remote[2]).name, rel_date_remote[2], None, "download"),
        NewVersion(Path(pip_version_remote[0]).name, rel_date_remote[0], None, "download"),
    ]

    download_wheel = mock_download(mocker, pip_version_remote)

    rel_date_gen = iter(rel_date_remote)
    release_date = mocker.patch(
        "virtualenv.seed.wheels.periodic_update.release_date_for_wheel_path",
        side_effect=lambda *a, **k: next(rel_date_gen),  # noqa: ARG005
    )

    last_update = _UP_NOW - timedelta(days=14)
    u_log = UpdateLog(
        started=last_update,
        completed=last_update,
        versions=downloaded_versions,
        periodic=True,
    )
    read_dict = mocker.patch("virtualenv.app_data.via_disk_folder.JSONStoreDisk.read", return_value=u_log.to_dict())
    write = mocker.patch("virtualenv.app_data.via_disk_folder.JSONStoreDisk.write")

    do_update("pip", "3.9", str(wheel.path), str(app_data_outer), [], True)

    assert download_wheel.call_count == 2
    assert release_date.call_count == 2
    assert read_dict.call_count == 1
    assert write.call_count == 1
    wrote_json = write.call_args[0][0]
    assert wrote_json["versions"] == [
        {
            "filename": Path(pip_version_remote[0]).name,
            "release_date": dump_datetime(rel_date_remote[0]),
            "found_date": dump_datetime(_UP_NOW),
            "source": "periodic",
        },
        {
            "filename": Path(pip_version_remote[1]).name,
            "release_date": dump_datetime(rel_date_remote[1]),
            "found_date": dump_datetime(_UP_NOW),
            "source": "periodic",
        },
        downloaded_versions[0].to_dict(),
    ]
