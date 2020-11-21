from __future__ import absolute_import, unicode_literals

import contextlib
import os
import subprocess
import sys
from stat import S_IWGRP, S_IWOTH, S_IWUSR
from threading import Thread

import pytest

from virtualenv.discovery import cached_py_info
from virtualenv.discovery.py_info import PythonInfo
from virtualenv.info import fs_supports_symlink
from virtualenv.run import cli_run
from virtualenv.seed.wheels.embed import BUNDLE_FOLDER, BUNDLE_SUPPORT
from virtualenv.util.path import safe_delete
from virtualenv.util.six import ensure_text
from virtualenv.util.subprocess import Popen


@pytest.mark.slow
@pytest.mark.parametrize("copies", [False, True] if fs_supports_symlink() else [True])
def test_seed_link_via_app_data(tmp_path, coverage_env, current_fastest, copies):
    current = PythonInfo.current_system()
    bundle_ver = BUNDLE_SUPPORT[current.version_release_str]
    create_cmd = [
        ensure_text(str(tmp_path / "en v")),  # space in the name to ensure generated scripts work when path has space
        "--no-periodic-update",
        "--seeder",
        "app-data",
        "--extra-search-dir",
        ensure_text(str(BUNDLE_FOLDER)),
        "--download",
        "--pip",
        bundle_ver["pip"].split("-")[1],
        "--setuptools",
        bundle_ver["setuptools"].split("-")[1],
        "--reset-app-data",
        "--creator",
        current_fastest,
        "-vv",
    ]
    if not copies:
        create_cmd.append("--symlink-app-data")
    result = cli_run(create_cmd)
    coverage_env()
    assert result

    # uninstalling pip/setuptools now should leave us with a ensure_safe_to_do env
    site_package = result.creator.purelib
    pip = site_package / "pip"
    setuptools = site_package / "setuptools"

    files_post_first_create = list(site_package.iterdir())
    assert pip in files_post_first_create
    assert setuptools in files_post_first_create
    for pip_exe in [
        result.creator.script_dir / "pip{}{}".format(suffix, result.creator.exe.suffix)
        for suffix in (
            "",
            "{}".format(current.version_info.major),
            "{}.{}".format(current.version_info.major, current.version_info.minor),
            "-{}.{}".format(current.version_info.major, current.version_info.minor),
        )
    ]:
        assert pip_exe.exists()
        process = Popen([ensure_text(str(pip_exe)), "--version", "--disable-pip-version-check"])
        _, __ = process.communicate()
        assert not process.returncode

    remove_cmd = [
        str(result.creator.script("pip")),
        "--verbose",
        "--disable-pip-version-check",
        "uninstall",
        "-y",
        "setuptools",
    ]
    process = Popen(remove_cmd)
    _, __ = process.communicate()
    assert not process.returncode
    assert site_package.exists()

    files_post_first_uninstall = list(site_package.iterdir())
    assert pip in files_post_first_uninstall
    assert setuptools not in files_post_first_uninstall

    # check we can run it again and will work - checks both overwrite and reuse cache
    result = cli_run(create_cmd)
    coverage_env()
    assert result
    files_post_second_create = list(site_package.iterdir())
    assert files_post_first_create == files_post_second_create

    # Windows does not allow removing a executable while running it, so when uninstalling pip we need to do it via
    # python -m pip
    remove_cmd = [str(result.creator.exe), "-m", "pip"] + remove_cmd[1:]
    process = Popen(remove_cmd + ["pip", "wheel"])
    _, __ = process.communicate()
    assert not process.returncode
    # pip is greedy here, removing all packages removes the site-package too
    if site_package.exists():
        purelib = result.creator.purelib
        patch_files = {purelib / "{}.{}".format("_virtualenv", i) for i in ("py", "pyc", "pth")}
        patch_files.add(purelib / "__pycache__")
        post_run = set(site_package.iterdir()) - patch_files
        assert not post_run, "\n".join(str(i) for i in post_run)

    if sys.version_info[0:2] == (3, 4) and os.environ.get(str("PIP_REQ_TRACKER")):
        os.environ.pop(str("PIP_REQ_TRACKER"))


@contextlib.contextmanager
def read_only_dir(d):
    write = S_IWUSR | S_IWGRP | S_IWOTH
    for root, _, filenames in os.walk(str(d)):
        os.chmod(root, os.stat(root).st_mode & ~write)
        for filename in filenames:
            filename = os.path.join(root, filename)
            os.chmod(filename, os.stat(filename).st_mode & ~write)
    try:
        yield
    finally:
        for root, _, filenames in os.walk(str(d)):
            os.chmod(root, os.stat(root).st_mode | write)
            for filename in filenames:
                filename = os.path.join(root, filename)
                os.chmod(filename, os.stat(filename).st_mode | write)


@pytest.fixture()
def read_only_app_data(temp_app_data):
    temp_app_data.mkdir()
    with read_only_dir(temp_app_data):
        yield temp_app_data


@pytest.mark.skipif(sys.platform == "win32", reason="Windows only applies R/O to files")
def test_base_bootstrap_link_via_app_data_not_writable(tmp_path, current_fastest, read_only_app_data, monkeypatch):
    dest = tmp_path / "venv"
    result = cli_run(["--seeder", "app-data", "--creator", current_fastest, "-vv", str(dest)])
    assert result


@pytest.mark.skipif(sys.platform == "win32", reason="Windows only applies R/O to files")
def test_populated_read_only_cache_and_symlinked_app_data(tmp_path, current_fastest, temp_app_data, monkeypatch):
    dest = tmp_path / "venv"
    cmd = [
        "--seeder",
        "app-data",
        "--creator",
        current_fastest,
        "--symlink-app-data",
        "-vv",
        str(dest),
    ]

    assert cli_run(cmd)
    subprocess.check_call((str(dest.joinpath("bin/python")), "-c", "import pip"))

    cached_py_info._CACHE.clear()  # necessary to re-trigger py info discovery
    safe_delete(dest)

    # should succeed with special flag when read-only
    with read_only_dir(temp_app_data):
        assert cli_run(["--read-only-app-data"] + cmd)
        subprocess.check_call((str(dest.joinpath("bin/python")), "-c", "import pip"))


@pytest.mark.skipif(sys.platform == "win32", reason="Windows only applies R/O to files")
def test_populated_read_only_cache_and_copied_app_data(tmp_path, current_fastest, temp_app_data, monkeypatch):
    dest = tmp_path / "venv"
    cmd = [
        "--seeder",
        "app-data",
        "--creator",
        current_fastest,
        "-vv",
        "-p",
        "python",
        str(dest),
    ]

    assert cli_run(cmd)

    cached_py_info._CACHE.clear()  # necessary to re-trigger py info discovery
    safe_delete(dest)

    # should succeed with special flag when read-only
    with read_only_dir(temp_app_data):
        assert cli_run(["--read-only-app-data"] + cmd)


@pytest.mark.slow
@pytest.mark.parametrize("pkg", ["pip", "setuptools", "wheel"])
def test_base_bootstrap_link_via_app_data_no(tmp_path, coverage_env, current_fastest, session_app_data, pkg):
    create_cmd = [str(tmp_path), "--seeder", "app-data", "--no-{}".format(pkg)]
    result = cli_run(create_cmd)
    assert not (result.creator.purelib / pkg).exists()
    for key in {"pip", "setuptools", "wheel"} - {pkg}:
        assert (result.creator.purelib / key).exists()


def test_app_data_parallel_ok(tmp_path, temp_app_data):
    exceptions = _run_parallel_threads(tmp_path)
    assert not exceptions, "\n".join(exceptions)


def test_app_data_parallel_fail(tmp_path, temp_app_data, mocker):
    mocker.patch("virtualenv.seed.embed.via_app_data.pip_install.base.PipInstall.build_image", side_effect=RuntimeError)
    exceptions = _run_parallel_threads(tmp_path)
    assert len(exceptions) == 2
    for exception in exceptions:
        assert exception.startswith("failed to build image wheel because:\nTraceback")
        assert "RuntimeError" in exception, exception


def _run_parallel_threads(tmp_path):
    exceptions = []

    def _run(name):
        try:
            cli_run(["--seeder", "app-data", str(tmp_path / name), "--no-pip", "--no-setuptools"])
        except Exception as exception:  # noqa
            as_str = str(exception)
            exceptions.append(as_str)

    threads = [Thread(target=_run, args=("env{}".format(i),)) for i in range(1, 3)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    return exceptions
