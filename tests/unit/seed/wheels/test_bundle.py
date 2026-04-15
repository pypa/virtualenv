from __future__ import annotations

import hashlib
import os
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

from virtualenv.app_data import AppDataDiskFolder
from virtualenv.seed.wheels import embed
from virtualenv.seed.wheels.bundle import from_bundle
from virtualenv.seed.wheels.embed import (
    BUNDLE_FOLDER,
    BUNDLE_SHA256,
    BUNDLE_SUPPORT,
    _verify_bundled_wheel,
    get_embed_wheel,
)
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


def test_version_embed(app_data, for_py_version) -> None:
    wheel = from_bundle("pip", Version.embed, for_py_version, [], app_data, False, os.environ)
    assert wheel is not None
    assert wheel.name == get_embed_wheel("pip", for_py_version).name


def test_version_bundle(app_data, for_py_version, next_pip_wheel) -> None:
    wheel = from_bundle("pip", Version.bundle, for_py_version, [], app_data, False, os.environ)
    assert wheel is not None
    assert wheel.name == next_pip_wheel.name


def test_version_pinned_not_found(app_data, for_py_version) -> None:
    wheel = from_bundle("pip", "0.0.0", for_py_version, [], app_data, False, os.environ)
    assert wheel is None


def test_version_pinned_is_embed(app_data, for_py_version) -> None:
    expected_wheel = get_embed_wheel("pip", for_py_version)
    wheel = from_bundle("pip", expected_wheel.version, for_py_version, [], app_data, False, os.environ)
    assert wheel is not None
    assert wheel.name == expected_wheel.name


def test_version_pinned_in_app_data(app_data, for_py_version, next_pip_wheel) -> None:
    wheel = from_bundle("pip", next_pip_wheel.version, for_py_version, [], app_data, False, os.environ)
    assert wheel is not None
    assert wheel.name == next_pip_wheel.name


def test_every_bundled_wheel_has_sha256() -> None:
    referenced = {wheel for mapping in BUNDLE_SUPPORT.values() for wheel in mapping.values()}
    missing = referenced - BUNDLE_SHA256.keys()
    assert not missing, f"bundled wheels missing from BUNDLE_SHA256: {sorted(missing)}"


def test_every_wheel_on_disk_has_sha256() -> None:
    on_disk = {entry.name for entry in BUNDLE_FOLDER.iterdir() if entry.suffix == ".whl"}
    assert on_disk == BUNDLE_SHA256.keys()


def test_get_embed_wheel_verifies_pip(for_py_version: str) -> None:
    wheel = get_embed_wheel("pip", for_py_version)
    assert wheel is not None


def test_verify_bundled_wheel_rejects_tamper(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake_name = "fake-0.0.1-py3-none-any.whl"
    fake = tmp_path / fake_name
    fake.write_bytes(b"not the real bytes")
    monkeypatch.setitem(BUNDLE_SHA256, fake_name, "0" * 64)
    monkeypatch.setattr("virtualenv.seed.wheels.embed._VERIFIED_WHEELS", set())

    with pytest.raises(RuntimeError, match="sha256 mismatch"):
        _verify_bundled_wheel(fake)


def test_verify_bundled_wheel_rejects_unknown(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    stray = tmp_path / "stray-0.0.1-py3-none-any.whl"
    stray.write_bytes(b"payload")
    monkeypatch.setattr("virtualenv.seed.wheels.embed._VERIFIED_WHEELS", set())

    with pytest.raises(RuntimeError, match="no recorded sha256"):
        _verify_bundled_wheel(stray)


def test_verify_bundled_wheel_reads_from_zipapp(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Simulate the layout we get when virtualenv runs out of a ``.pyz``: the wheel lives inside the zipapp rather
    # than on disk, so the hash check has to read it through ``zipfile`` rather than ``path.open``.
    wheel_name = "fakepkg-0.0.1-py3-none-any.whl"
    wheel_payload = b"pretend-wheel-bytes"
    fake_root = tmp_path / "virtualenv.pyz"
    entry = f"virtualenv/seed/wheels/embed/{wheel_name}"
    with zipfile.ZipFile(str(fake_root), "w") as archive:
        archive.writestr(entry, wheel_payload)

    monkeypatch.setattr(embed, "IS_ZIPAPP", True)
    monkeypatch.setattr(embed, "ROOT", str(fake_root))
    monkeypatch.setitem(BUNDLE_SHA256, wheel_name, hashlib.sha256(wheel_payload).hexdigest())
    monkeypatch.setattr(embed, "_VERIFIED_WHEELS", set())

    _verify_bundled_wheel(fake_root / entry)
