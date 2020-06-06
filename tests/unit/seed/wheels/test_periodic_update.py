from datetime import datetime, timedelta

from virtualenv.seed.wheels.embed import BUNDLE_SUPPORT, get_embed_wheel
from virtualenv.seed.wheels.periodic_update import NewVersion, manual_upgrade


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
