from __future__ import absolute_import, unicode_literals

import os
import sys

import pytest
import six

from virtualenv.discovery.py_info import PythonInfo
from virtualenv.info import fs_supports_symlink
from virtualenv.run import cli_run
from virtualenv.seed.embed.wheels import BUNDLE_SUPPORT
from virtualenv.seed.embed.wheels.acquire import BUNDLE_FOLDER
from virtualenv.util.subprocess import Popen


@pytest.mark.slow
@pytest.mark.parametrize("copies", [True, False] if fs_supports_symlink() else [True])
def test_base_bootstrap_link_via_app_data(tmp_path, coverage_env, current_fastest, copies):
    current = PythonInfo.current_system()
    bundle_ver = BUNDLE_SUPPORT[current.version_release_str]
    create_cmd = [
        six.ensure_text(str(tmp_path / "env")),
        "--seeder",
        "app-data",
        "--extra-search-dir",
        six.ensure_text(str(BUNDLE_FOLDER)),
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
            "-{}.{}".format(current.version_info.major, current.version_info.minor),
        )
    ]:
        assert pip_exe.exists()
        process = Popen([six.ensure_text(str(pip_exe)), "--version", "--disable-pip-version-check"])
        _, __ = process.communicate()
        assert not process.returncode

    remove_cmd = [
        str(result.creator.exe),
        "-m",
        "pip",
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

    process = Popen(remove_cmd + ["pip", "wheel"])
    _, __ = process.communicate()
    assert not process.returncode
    # pip is greedy here, removing all packages removes the site-package too
    if site_package.exists():
        post_run = list(site_package.iterdir())
        assert not post_run, "\n".join(str(i) for i in post_run)

    if sys.version_info[0:2] == (3, 4) and os.environ.get(str("PIP_REQ_TRACKER")):
        os.environ.pop(str("PIP_REQ_TRACKER"))
