from __future__ import absolute_import, unicode_literals

from datetime import datetime, timedelta

from six.moves import zip_longest

from virtualenv import cli_run
from virtualenv.seed.wheels.embed import BUNDLE_SUPPORT, get_embed_wheel
from virtualenv.seed.wheels.periodic_update import NewVersion, UpdateLog, manual_upgrade, periodic_update


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
