from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

import pytest

from virtualenv.app_data import AppDataDiskFolder
from virtualenv.seed.wheels.bundle import from_bundle
from virtualenv.seed.wheels.embed import get_embed_wheel
from virtualenv.seed.wheels.periodic_update import dump_datetime
from virtualenv.seed.wheels.util import Version, Wheel


@pytest.fixture(scope="module")
def next_pip_wheel(for_py_version):
    wheel = get_embed_wheel("pip", for_py_version)
    new_version = list(wheel.version_tuple)
    new_version[-1] += 1
    new_name = wheel.name.replace(wheel.version, ".".join(str(i) for i in new_version))
    return Wheel.from_path(Path(new_name))


@pytest.fixture(scope="module")
def app_data(tmp_path_factory, for_py_version, next_pip_wheel):
    temp_folder = tmp_path_factory.mktemp("module-app-data")
    now = dump_datetime(datetime.now(tz=timezone.utc))
    app_data_ = AppDataDiskFolder(str(temp_folder))
    app_data_.embed_update_log("pip", for_py_version).write(
        {
            "completed": now,
            "periodic": True,
            "started": now,
            "versions": [
                {
                    "filename": next_pip_wheel.name,
                    "found_date": "2000-01-01T00:00:00.000000Z",
                    "release_date": "2000-01-01T00:00:00.000000Z",
                    "source": "periodic",
                },
            ],
        },
    )
    return app_data_


def test_version_embed(app_data, for_py_version):
    wheel = from_bundle("pip", Version.embed, for_py_version, [], app_data, False, os.environ)
    assert wheel is not None
    assert wheel.name == get_embed_wheel("pip", for_py_version).name


def test_version_bundle(app_data, for_py_version, next_pip_wheel):
    wheel = from_bundle("pip", Version.bundle, for_py_version, [], app_data, False, os.environ)
    assert wheel is not None
    assert wheel.name == next_pip_wheel.name


def test_version_pinned_not_found(app_data, for_py_version):
    wheel = from_bundle("pip", "0.0.0", for_py_version, [], app_data, False, os.environ)
    assert wheel is None


def test_version_pinned_is_embed(app_data, for_py_version):
    expected_wheel = get_embed_wheel("pip", for_py_version)
    wheel = from_bundle("pip", expected_wheel.version, for_py_version, [], app_data, False, os.environ)
    assert wheel is not None
    assert wheel.name == expected_wheel.name


def test_version_pinned_in_app_data(app_data, for_py_version, next_pip_wheel):
    wheel = from_bundle("pip", next_pip_wheel.version, for_py_version, [], app_data, False, os.environ)
    assert wheel is not None
    assert wheel.name == next_pip_wheel.name
