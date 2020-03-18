from __future__ import absolute_import, unicode_literals

import os
import sys
from stat import S_IREAD, S_IRGRP, S_IROTH, S_IWUSR

import pytest

from virtualenv.discovery.py_info import PythonInfo
from virtualenv.info import fs_supports_symlink
from virtualenv.run import cli_run
from virtualenv.seed.embed.wheels import BUNDLE_SUPPORT
from virtualenv.seed.embed.wheels.acquire import BUNDLE_FOLDER
from virtualenv.util.six import ensure_text
from virtualenv.util.subprocess import Popen


@pytest.mark.slow
@pytest.mark.timeout(timeout=60)
@pytest.mark.parametrize("copies", [False, True] if fs_supports_symlink() else [True])
def test_seed_link_via_app_data(tmp_path, coverage_env, current_fastest, copies):
    current = PythonInfo.current_system()
    bundle_ver = BUNDLE_SUPPORT[current.version_release_str]
    create_cmd = [
        ensure_text(str(tmp_path / "en v")),  # space in the name to ensure generated scripts work when path has space
        "--seeder",
        "app-data",
        "--extra-search-dir",
        ensure_text(str(BUNDLE_FOLDER)),
        "--download",
        "--pip",
        bundle_ver["pip"].split("-")[1],
        "--setuptools",
        bundle_ver["setuptools"].split("-")[1],
        "--clear-app-data",
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


@pytest.fixture()
def read_only_folder(temp_app_data):
    temp_app_data.mkdir()
    try:
        os.chmod(str(temp_app_data), S_IREAD | S_IRGRP | S_IROTH)
        yield temp_app_data
    finally:
        os.chmod(str(temp_app_data), S_IWUSR | S_IREAD)


@pytest.mark.skipif(sys.platform == "win32", reason="Windows only applies R/O to files")
def test_base_bootstrap_link_via_app_data_not_writable(tmp_path, current_fastest, read_only_folder, monkeypatch):
    dest = tmp_path / "venv"
    result = cli_run(["--seeder", "app-data", "--creator", current_fastest, "--clear-app-data", "-vv", str(dest)])
    assert result


@pytest.mark.slow
@pytest.mark.timeout(timeout=60)
@pytest.mark.parametrize("pkg", ["pip", "setuptools", "wheel"])
def test_base_bootstrap_link_via_app_data_no(tmp_path, coverage_env, current_fastest, session_app_data, pkg):
    create_cmd = [str(tmp_path), "--seeder", "app-data", "--no-{}".format(pkg)]
    result = cli_run(create_cmd)
    assert not (result.creator.purelib / pkg).exists()
    for key in {"pip", "setuptools", "wheel"} - {pkg}:
        assert (result.creator.purelib / key).exists()
