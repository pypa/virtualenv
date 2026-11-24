from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import sysconfig
from dataclasses import dataclass
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from subprocess import CalledProcessError, Popen
from typing import TYPE_CHECKING, Final
from zipfile import ZipFile

import pytest

from virtualenv.app_data import AppDataDiskFolder, make_app_data
from virtualenv.seed.wheels.acquire import PIP_RUN, download_wheel, get_wheel, pip_wheel_env_run
from virtualenv.seed.wheels.embed import BUNDLE_FOLDER, MAX, MIN, get_embed_wheel
from virtualenv.seed.wheels.periodic_update import UnverifiedWheelError, dump_datetime
from virtualenv.seed.wheels.util import Wheel

if TYPE_CHECKING:
    from collections.abc import Callable
    from ssl import SSLContext

    from pytest_mock import MockerFixture, MockType


@pytest.fixture(autouse=True)
def _fake_release_date(mocker) -> None:
    mocker.patch("virtualenv.seed.wheels.periodic_update.release_date_for_wheel_path", return_value=None, autospec=True)


def test_pip_wheel_env_run_could_not_find(session_app_data, mocker) -> None:
    mocker.patch("virtualenv.seed.wheels.acquire.from_bundle", return_value=None, autospec=True)
    with pytest.raises(RuntimeError, match="could not find the embedded pip"):
        pip_wheel_env_run([], session_app_data, os.environ)


@pytest.mark.parametrize("for_py_version", [MIN, MAX])
def test_pip_wheel_env_run_uses_pip_for_target_version(session_app_data, for_py_version: str) -> None:
    env: Final[dict[str, str]] = pip_wheel_env_run([], session_app_data, os.environ, for_py_version)

    assert (Path(env["VIRTUALENV_PIP_WHEEL"]).name, "PYTHONPATH" in env) == (
        get_embed_wheel("pip", for_py_version).name,
        False,
    )


def test_pip_helper_keeps_wheel_path_with_separator(tmp_path: Path) -> None:
    prefix = tmp_path / "date"
    prefix.mkdir()
    marker = tmp_path / "sitecustomize-ran"
    (prefix / "sitecustomize.py").write_text(
        f"from pathlib import Path\nPath({str(marker)!r}).write_text('ran')\n", encoding="utf-8"
    )
    search_dir = tmp_path / f"date{os.pathsep}time" / "wheels"
    search_dir.mkdir(parents=True)
    wheel = search_dir / "pip-99.0-py3-none-any.whl"
    embedded = get_embed_wheel("pip", f"{sys.version_info.major}.{sys.version_info.minor}")
    with ZipFile(embedded.path) as source, ZipFile(wheel, "w") as target:
        for name in source.namelist():
            content = source.read(name)
            if name.endswith(".dist-info/METADATA"):
                content = content.replace(f"Version: {embedded.version}".encode(), b"Version: 99.0")
            target.writestr(name.replace(f"pip-{embedded.version}.dist-info", "pip-99.0.dist-info"), content)
    env = pip_wheel_env_run([search_dir], AppDataDiskFolder(str(tmp_path / "cache")), os.environ)

    result = subprocess.run(
        [sys.executable, "-c", PIP_RUN, "--version"],
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )

    assert (str(wheel) in result.stdout, marker.exists()) == (True, False)


@pytest.mark.parametrize(
    "version_spec",
    [
        pytest.param(lambda _wheel: None, id="latest"),
        pytest.param(lambda _wheel: "", id="unpinned"),
        pytest.param(lambda wheel: f"=={wheel.version}", id="pinned"),
    ],
)
def test_download_wheel_uses_staged_archive(
    download_process: _DownloadProcess,
    for_py_version: str,
    session_app_data: AppDataDiskFolder,
    tmp_path: Path,
    version_spec: Callable[[Wheel], str | None],
) -> None:
    expected = download_process.wheel
    result: Final[Wheel] = download_wheel(
        "pip", version_spec(expected), for_py_version, [], session_app_data, tmp_path, {}
    )
    assert (result.path, result.path.read_bytes(), list(tmp_path.iterdir())) == (
        tmp_path / expected.name,
        expected.path.read_bytes(),
        [tmp_path / expected.name],
    )


def test_download_wheel_not_found_raises(
    download_process: _DownloadProcess,
    for_py_version: str,
    session_app_data: AppDataDiskFolder,
    tmp_path: Path,
) -> None:
    download_process.process.side_effect = None
    with pytest.raises(RuntimeError, match="could not find downloaded wheel"):
        download_wheel("pip", None, for_py_version, [], session_app_data, tmp_path, {})
    assert list(tmp_path.iterdir()) == []


@pytest.mark.usefixtures("download_process")
def test_download_wheel_rejects_wrong_version(
    for_py_version: str,
    session_app_data: AppDataDiskFolder,
    tmp_path: Path,
) -> None:
    with pytest.raises(RuntimeError, match="unexpected downloaded wheel"):
        download_wheel("pip", "==0.0.0", for_py_version, [], session_app_data, tmp_path, {})
    assert list(tmp_path.iterdir()) == []


@pytest.mark.usefixtures("download_process")
def test_download_wheel_rejects_unsupported_python(
    session_app_data: AppDataDiskFolder,
    tmp_path: Path,
) -> None:
    with pytest.raises(RuntimeError, match="does not support Python"):
        download_wheel("pip", None, "2.7", [], session_app_data, tmp_path, {})
    assert list(tmp_path.iterdir()) == []


def test_download_wheel_skips_local_pip_module(
    mocker: MockerFixture,
    for_py_version: str,
    session_app_data: AppDataDiskFolder,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (tmp_path / "pip").mkdir()
    (tmp_path / "pip" / "__init__.py").write_text("raise SystemExit('imported from the working directory')", "utf-8")
    monkeypatch.chdir(tmp_path)
    mocker.patch("virtualenv.seed.wheels.acquire.verify_wheel_digest", autospec=True)
    embedded: Final[Wheel | None] = get_embed_wheel("pip", for_py_version)
    env: Final[dict[str, str]] = {**os.environ, "PIP_NO_INDEX": "1", "PIP_FIND_LINKS": str(BUNDLE_FOLDER)}

    result: Final[Wheel] = download_wheel(
        "pip", f"=={embedded.version}", for_py_version, [], session_app_data, tmp_path / "house", env
    )

    assert result.path == tmp_path / "house" / embedded.name


@pytest.mark.skipif(sys.implementation.name != "cpython", reason="CPython startup import")
@pytest.mark.skipif(sys.version_info < (3, 11), reason="PYTHONSAFEPATH is new in Python 3.11")
def test_pip_helper_omits_current_directory_at_startup(session_app_data: AppDataDiskFolder, tmp_path: Path) -> None:
    marker = tmp_path / "loaded"
    (tmp_path / "linecache.py").write_text(
        "import os\n"
        "with open(os.environ['TEST_MARKER'], 'w', encoding='utf-8') as output: output.write('loaded')\n"
        "with open(os.environ['TEST_LINECACHE'], encoding='utf-8') as source: "
        "exec(compile(source.read(), source.name, 'exec'))\n",
        encoding="utf-8",
    )
    env = pip_wheel_env_run(
        [],
        session_app_data,
        {
            **{key: value for key, value in os.environ.items() if key != "PYTHONSAFEPATH"},
            "TEST_MARKER": str(marker),
            "TEST_LINECACHE": str(Path(sysconfig.get_path("stdlib")) / "linecache.py"),
        },
    )
    # The tox Python loads coverage code before the helper source.
    result = subprocess.run(
        [
            sys._base_executable,  # ruff: ignore[private-member-access]  # Homebrew lacks BINDIR/python
            "-c",
            PIP_RUN,
            "--version",
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
        timeout=10,
    )

    assert (
        get_embed_wheel("pip", f"{sys.version_info.major}.{sys.version_info.minor}").name in result.stdout,
        marker.exists(),
    ) == (
        True,
        False,
    )


def test_download_fails(
    download_process: _DownloadProcess,
    for_py_version: str,
    session_app_data: AppDataDiskFolder,
    tmp_path: Path,
) -> None:
    download_process.process.return_value.configure_mock(returncode=7)
    with pytest.raises(CalledProcessError) as context:
        download_wheel("pip", None, for_py_version, [], session_app_data, tmp_path, {})
    error: Final[CalledProcessError] = context.value
    assert (error.output, error.stderr, error.returncode, error.cmd[:3], list(tmp_path.iterdir())) == (
        "progress complete",
        "",
        7,
        [sys.executable, "-c", PIP_RUN],
        [],
    )


def test_download_wheel_python_io_encoding(
    download_process: _DownloadProcess,
    for_py_version: str,
    session_app_data: AppDataDiskFolder,
    tmp_path: Path,
) -> None:
    download_wheel("pip", None, for_py_version, [], session_app_data, tmp_path, {})
    assert download_process.process.call_args.kwargs["env"]["PYTHONIOENCODING"] == "utf-8"


def test_download_wheel_keeps_failed_verification_out_of_cache(
    download_process: _DownloadProcess,
    for_py_version: str,
    session_app_data: AppDataDiskFolder,
    tmp_path: Path,
) -> None:
    download_process.payload += b"\n"
    with pytest.raises(RuntimeError, match="but PyPI reports"):
        download_wheel("pip", None, for_py_version, [], session_app_data, tmp_path, {})
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize(
    "env_var",
    [
        pytest.param(name, id=name.lower())
        for name in (
            "PIP_INDEX_URL",
            "PIP_EXTRA_INDEX_URL",
            "PIP_INDEX",
        )
    ],
)
def test_download_wheel_preserves_custom_index_policy(
    download_process: _DownloadProcess,
    for_py_version: str,
    session_app_data: AppDataDiskFolder,
    tmp_path: Path,
    env_var: str,
) -> None:
    download_process.payload += b"\n"
    result: Final[Wheel] = download_wheel(
        "pip",
        None,
        for_py_version,
        [],
        session_app_data,
        tmp_path,
        {env_var: "https://index.example/simple"},
    )
    assert result.path.read_bytes() == download_process.payload


@pytest.fixture
def download_process(mocker: MockerFixture, for_py_version: str) -> _DownloadProcess:
    wheel: Final[Wheel | None] = get_embed_wheel("pip", for_py_version)
    assert wheel is not None
    payload = wheel.path.read_bytes()
    metadata: Final[bytes] = json.dumps({
        "releases": {
            wheel.version: [
                {
                    "filename": wheel.name,
                    "digests": {"sha256": hashlib.sha256(payload).hexdigest()},
                }
            ]
        }
    }).encode()

    def metadata_response(*_args: str, **_kwargs: SSLContext | int | None) -> BytesIO:
        return BytesIO(metadata)

    mocker.patch("virtualenv.seed.wheels.periodic_update.urlopen", autospec=True, side_effect=metadata_response)

    def downloaded(cmd: list[str], **_kwargs: str | int | bool | dict[str, str]) -> Popen[str]:
        (Path(cmd[cmd.index("-d") + 1]) / wheel.name).write_bytes(download.payload)
        return process.return_value

    process: Final[MockType] = mocker.patch(
        "virtualenv.seed.wheels.acquire.Popen", autospec=True, side_effect=downloaded
    )
    process.return_value.configure_mock(**{"communicate.return_value": ("progress complete", ""), "returncode": 0})
    download = _DownloadProcess(process, wheel, payload)
    return download


@dataclass
class _DownloadProcess:
    process: MockType
    wheel: Wheel
    payload: bytes


@pytest.fixture
def downloaded_wheel(mocker):
    wheel = Wheel.from_path(Path("setuptools-0.0.0-py2.py3-none-any.whl"))
    return wheel, mocker.patch("virtualenv.seed.wheels.acquire.download_wheel", return_value=wheel, autospec=True)


@pytest.mark.parametrize("version", ["bundle", "0.0.0"])
def test_get_wheel_download_called(mocker, for_py_version, session_app_data, downloaded_wheel, version) -> None:
    write = mocker.patch("virtualenv.app_data.via_disk_folder.JSONStoreDisk.write", autospec=True)
    wheel = get_wheel("setuptools", version, for_py_version, [], True, session_app_data, False, os.environ)
    assert wheel is not None
    assert wheel.name == downloaded_wheel[0].name
    assert downloaded_wheel[1].call_count == 1
    assert write.call_count == 1


@pytest.mark.parametrize("version", ["embed", "pinned"])
def test_get_wheel_download_not_called(mocker, for_py_version, session_app_data, downloaded_wheel, version) -> None:
    distribution = "setuptools"
    expected = get_embed_wheel(distribution, for_py_version)
    version = {"embed": "embed", "pinned": expected.version}[version]
    write = mocker.patch("virtualenv.app_data.via_disk_folder.JSONStoreDisk.write", autospec=True)
    wheel = get_wheel(distribution, version, for_py_version, [], True, session_app_data, False, os.environ)
    assert wheel is not None
    assert wheel.name == expected.name
    assert downloaded_wheel[1].call_count == 0
    assert write.call_count == 0


def test_get_wheel_falls_back_to_bundle_when_unverified(
    mocker: MockerFixture, for_py_version: str, session_app_data: AppDataDiskFolder
) -> None:
    mocker.patch(
        "virtualenv.seed.wheels.acquire.download_wheel", side_effect=UnverifiedWheelError("refusing"), autospec=True
    )

    wheel = get_wheel("setuptools", "bundle", for_py_version, [], True, session_app_data, False, os.environ)

    assert wheel is not None
    assert wheel.name == get_embed_wheel("setuptools", for_py_version).name


def test_get_wheel_unverified_pinned_version_fails(
    mocker: MockerFixture, for_py_version: str, session_app_data: AppDataDiskFolder
) -> None:
    mocker.patch(
        "virtualenv.seed.wheels.acquire.download_wheel", side_effect=UnverifiedWheelError("refusing"), autospec=True
    )

    with pytest.raises(UnverifiedWheelError, match="refusing"):
        get_wheel("setuptools", "0.0.0", for_py_version, [], True, session_app_data, False, os.environ)


@pytest.mark.parametrize(
    ("folder", "override", "reusable"),
    [
        pytest.param(None, {}, False, id="default"),
        pytest.param("cache", {}, True, id="explicit"),
        pytest.param(None, {"VIRTUALENV_OVERRIDE_APP_DATA": "cache"}, True, id="override"),
    ],
)
def test_custom_wheel_offline_lookup_requires_explicit_cache(  # ruff:ignore[too-many-arguments]  # fixtures and cache options
    tmp_path: Path,
    mocker: MockerFixture,
    monkeypatch: pytest.MonkeyPatch,
    folder: str | None,
    override: dict[str, str],
    reusable: bool,
) -> None:
    monkeypatch.chdir(tmp_path)
    mocker.patch("virtualenv.app_data.cache_dir_with_migration", autospec=True, return_value=str(tmp_path / "cache"))
    app_data = make_app_data(folder, read_only=False, env=override)
    name = "demo-1.0-py3-none-any.whl"

    def download(cmd: list[str], **_kwargs: object) -> MockType:
        with ZipFile(Path(cmd[cmd.index("-d") + 1]) / name, "w") as archive:
            archive.writestr("demo-1.0.dist-info/METADATA", "Name: demo\nVersion: 1.0\n")
        return process.return_value

    process = mocker.patch("virtualenv.seed.wheels.acquire.Popen", autospec=True, side_effect=download)
    process.return_value.configure_mock(**{"communicate.return_value": ("", ""), "returncode": 0})
    env = {"PIP_INDEX_URL": "https://packages.example/simple"}
    downloaded = get_wheel("demo", "1.0", "3.11", [], True, app_data, False, env)
    assert downloaded is not None
    assert app_data.for_wheel_index(env).embed_update_log("demo", "3.11").exists() == reusable
    selected = get_wheel("demo", "1.0", "3.11", [], False, app_data, False, {})
    assert (selected is not None) == reusable
    implicit = make_app_data(None, read_only=False, env={})
    assert get_wheel("demo", "1.0", "3.11", [], False, implicit, False, env) is None
    assert get_wheel("demo", "1.0", "3.11", [], False, implicit, False, {}) is None
    process.assert_called_once()


def test_pin_prefers_verified_or_bundled_wheel_over_private_build(
    tmp_path: Path, download_process: _DownloadProcess, for_py_version: str
) -> None:
    app_data = AppDataDiskFolder(str(tmp_path))
    verified = get_wheel("pip", "bundle", for_py_version, [], True, app_data, False, {})
    assert verified is not None
    data = BytesIO()
    with ZipFile(data, "w") as archive:
        archive.writestr(f"pip-{verified.version}.dist-info/METADATA", f"Name: pip\nVersion: {verified.version}\n")
    download_process.payload = data.getvalue()
    env = {"PIP_INDEX_URL": "https://packages.example/simple"}
    private = get_wheel("pip", "bundle", for_py_version, [], True, app_data, False, env)
    assert private is not None
    pinned = get_wheel("pip", verified.version, for_py_version, [], False, app_data, False, {})
    assert pinned is not None
    assert (pinned.path, pinned.path.read_bytes(), private.path.read_bytes()) == (
        verified.path,
        download_process.wheel.path.read_bytes(),
        data.getvalue(),
    )
    verified.path.unlink()
    bundled = get_wheel("pip", verified.version, for_py_version, [], False, app_data, False, {})
    assert bundled is not None
    assert bundled.path == download_process.wheel.path
    entry = app_data.for_wheel_index(env).embed_update_log("pip", for_py_version).read()["versions"][0]
    assert entry["verification"] == "UNVERIFIED"
    assert download_process.process.call_count == 2


def test_legacy_wheelhouse_and_update_records_are_ignored(tmp_path: Path) -> None:
    house = tmp_path / "wheel" / "house"
    house.mkdir(parents=True)
    filename = "demo-1.0-py3-none-any.whl"
    (house / filename).touch()
    log = tmp_path / "wheel" / "3.11" / "embed" / "3" / "demo.json"
    log.parent.mkdir(parents=True)
    log.write_text(
        json.dumps({
            "versions": [
                {
                    "filename": filename,
                    "found_date": "2025-01-01T00:00:00.000000Z",
                    "release_date": None,
                    "source": "manual",
                }
            ]
        }),
        encoding="utf-8",
    )

    assert get_wheel("demo", "1.0", "3.11", [], False, AppDataDiskFolder(str(tmp_path)), False, {}) is None


def test_get_wheel_download_cached(
    tmp_path: Path,
    mocker: MockerFixture,
    for_py_version: str,
    downloaded_wheel: tuple[Wheel, MockType],
    time_freeze: Callable[[datetime], None],
) -> None:
    time_freeze(datetime.now(tz=timezone.utc))
    # imported with the test, which needs only this store class
    from virtualenv.app_data.via_disk_folder import JSONStoreDisk  # ruff:ignore[import-outside-top-level]

    app_data = AppDataDiskFolder(folder=str(tmp_path))
    expected = downloaded_wheel[0]
    (app_data.house / expected.name).touch()
    write = mocker.spy(JSONStoreDisk, "write")
    # 1st call, not cached, download is called
    wheel = get_wheel(expected.distribution, expected.version, for_py_version, [], True, app_data, False, os.environ)
    assert wheel is not None
    assert wheel.name == expected.name
    assert downloaded_wheel[1].call_count == 1
    assert write.call_count == 1
    # 2nd call, cached, download is not called
    wheel = get_wheel(expected.distribution, expected.version, for_py_version, [], True, app_data, False, os.environ)
    assert wheel is not None
    assert wheel.name == expected.name
    assert downloaded_wheel[1].call_count == 1
    assert write.call_count == 1
    wrote_json = write.call_args[0][1]
    assert wrote_json == {
        "completed": None,
        "periodic": None,
        "started": None,
        "versions": [
            {
                "filename": expected.name,
                "release_date": None,
                "found_date": dump_datetime(datetime.now(tz=timezone.utc)),
                "source": "download",
            },
        ],
    }


@pytest.mark.parametrize(
    "distribution",
    [
        "pip space",
        "pip[extra]",
        "pip;os.system('x')",
        "--index-url=http://evil",
        "-r requirements.txt",
        "",
        ".pip",
        "pip-",
    ],
)
def test_download_wheel_rejects_bad_distribution(distribution: str, session_app_data) -> None:
    with pytest.raises(ValueError, match="suspicious distribution name"):
        download_wheel(distribution, None, "3.14", [], session_app_data, "folder", os.environ)


@pytest.mark.parametrize(
    "version_spec",
    [
        pytest.param("==1.0 --index-url=http://evil", id="extra-option"),
        pytest.param(">=1.0", id="unsupported-operator"),
        pytest.param("== 1.0", id="whitespace"),
        pytest.param("==1.0;echo", id="separator"),
        pytest.param("==not-a-version", id="invalid-version"),
        pytest.param("==1.zip", id="archive-version"),
    ],
)
def test_download_wheel_rejects_bad_version_spec(
    version_spec: str, session_app_data: AppDataDiskFolder, mocker: MockerFixture
) -> None:
    mocker.patch(
        "virtualenv.seed.wheels.acquire.Popen", autospec=True, side_effect=AssertionError("unexpected download")
    )
    with pytest.raises(ValueError, match="suspicious version spec"):
        download_wheel("pip", version_spec, "3.14", [], session_app_data, session_app_data.house, {})


@pytest.mark.parametrize(
    "suffix",
    [
        pytest.param(suffix, id=suffix)
        for suffix in (
            "zip",
            "whl",
            "tar",
            "tar.gz",
            "tgz",
            "tar.bz2",
            "tbz",
            "tar.xz",
            "txz",
            "tlz",
            "tar.lz",
            "tar.lzma",
            "ZIP",
        )
    ],
)
def test_download_wheel_rejects_archive_local_version(suffix: str, session_app_data: AppDataDiskFolder) -> None:
    with pytest.raises(ValueError, match="archive-like requirement"):
        download_wheel("pip", f"==1+local.{suffix}", "3.14", [], session_app_data, session_app_data.house, {})
