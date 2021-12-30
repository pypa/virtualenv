from __future__ import absolute_import, unicode_literals

import os
import sys
from subprocess import CalledProcessError

import pytest

from virtualenv.seed.wheels.acquire import download_wheel, get_wheel, pip_wheel_env_run
from virtualenv.seed.wheels.embed import BUNDLE_FOLDER, get_embed_wheel
from virtualenv.seed.wheels.util import Wheel, discover_wheels
from virtualenv.util.path import Path


def test_pip_wheel_env_run_could_not_find(session_app_data, mocker):
    mocker.patch("virtualenv.seed.wheels.acquire.from_bundle", return_value=None)
    with pytest.raises(RuntimeError, match="could not find the embedded pip"):
        pip_wheel_env_run([], session_app_data, os.environ)


def test_download_wheel_bad_output(mocker, for_py_version, session_app_data):
    """if the download contains no match for what wheel was downloaded, pick one that matches from target"""
    distribution = "setuptools"
    p_open = mocker.MagicMock()
    mocker.patch("virtualenv.seed.wheels.acquire.Popen", return_value=p_open)
    p_open.communicate.return_value = "", ""
    p_open.returncode = 0

    embed = get_embed_wheel(distribution, for_py_version)
    as_path = mocker.MagicMock()
    available = discover_wheels(BUNDLE_FOLDER, "setuptools", None, for_py_version)
    as_path.iterdir.return_value = [i.path for i in available]

    result = download_wheel(
        distribution, "=={}".format(embed.version), for_py_version, [], session_app_data, as_path, os.environ
    )
    assert result.path == embed.path


def test_download_fails(mocker, for_py_version, session_app_data):
    p_open = mocker.MagicMock()
    mocker.patch("virtualenv.seed.wheels.acquire.Popen", return_value=p_open)
    p_open.communicate.return_value = "out", "err"
    p_open.returncode = 1

    as_path = mocker.MagicMock()
    with pytest.raises(CalledProcessError) as context:
        download_wheel("pip", "==1", for_py_version, [], session_app_data, as_path, os.environ),
    exc = context.value
    if sys.version_info < (3, 5):
        assert exc.output == "outerr"
    else:
        assert exc.output == "out"
        assert exc.stderr == "err"
    assert exc.returncode == 1
    assert [
        sys.executable,
        "-m",
        "pip",
        "download",
        "--progress-bar",
        "off",
        "--disable-pip-version-check",
        "--only-binary=:all:",
        "--no-deps",
        "--python-version",
        for_py_version,
        "-d",
        str(as_path),
        "pip==1",
    ] == exc.cmd


@pytest.fixture
def downloaded_wheel(mocker):
    wheel = Wheel.from_path(Path("setuptools-0.0.0-py2.py3-none-any.whl"))
    mocker.patch("virtualenv.seed.wheels.acquire.download_wheel", return_value=wheel)
    yield wheel


@pytest.mark.parametrize("version", ["bundle", "0.0.0"])
def test_get_wheel_download_called(for_py_version, session_app_data, downloaded_wheel, version):
    distribution = "setuptools"
    wheel = get_wheel(distribution, version, for_py_version, [], True, session_app_data, False, os.environ)
    assert wheel is not None
    assert wheel.name == downloaded_wheel.name


@pytest.mark.parametrize("version", ["embed", "pinned"])
def test_get_wheel_download_not_called(for_py_version, session_app_data, downloaded_wheel, version):
    distribution = "setuptools"
    expected = get_embed_wheel(distribution, for_py_version)
    if version == "pinned":
        version = expected.version
    wheel = get_wheel(distribution, version, for_py_version, [], True, session_app_data, False, os.environ)
    assert wheel is not None
    assert wheel.name == expected.name
