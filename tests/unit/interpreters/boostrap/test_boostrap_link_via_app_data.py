from __future__ import absolute_import, unicode_literals

import os
import sys

import six

from virtualenv.interpreters.discovery.py_info import CURRENT
from virtualenv.run import run_via_cli
from virtualenv.seed.embed.wheels import BUNDLE_SUPPORT
from virtualenv.util.subprocess import Popen


def test_base_bootstrap_link_via_app_data(tmp_path, coverage_env):
    bundle_ver = BUNDLE_SUPPORT[CURRENT.version_release_str]
    create_cmd = [
        str(tmp_path / "env"),
        "--seeder",
        "link-app-data",
        "--download",
        "--pip",
        bundle_ver["pip"].split("-")[1],
        "--setuptools",
        bundle_ver["setuptools"].split("-")[1],
    ]
    result = run_via_cli(create_cmd)
    coverage_env()
    assert result

    # uninstalling pip/setuptools now should leave us with a clean env
    site_package = result.creator.site_packages[0]
    pip = site_package / "pip"
    setuptools = site_package / "setuptools"

    files_post_first_create = list(site_package.iterdir())
    assert pip in files_post_first_create
    assert setuptools in files_post_first_create

    env_exe = result.creator.exe
    for pip_exe in [
        env_exe.with_name("pip{}{}".format(suffix, env_exe.suffix))
        for suffix in (
            "",
            "{}".format(CURRENT.version_info.major),
            "-{}.{}".format(CURRENT.version_info.major, CURRENT.version_info.minor),
        )
    ]:
        assert pip_exe.exists()
        process = Popen([six.ensure_text(str(pip_exe)), "--version", "--disable-pip-version-check"])
        _, __ = process.communicate()
        assert not process.returncode

    remove_cmd = [
        str(env_exe),
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
    result = run_via_cli(create_cmd)
    coverage_env()
    assert result
    files_post_second_create = list(site_package.iterdir())
    assert files_post_first_create == files_post_second_create

    process = Popen(remove_cmd + ["pip"])
    _, __ = process.communicate()
    assert not process.returncode
    # pip is greedy here, removing all packages removes the site-package too
    if site_package.exists():
        post_run = list(site_package.iterdir())
        assert not post_run, "\n".join(str(i) for i in post_run)

    if sys.version_info[0:2] == (3, 4) and "PIP_REQ_TRACKER" in os.environ:
        os.environ.pop("PIP_REQ_TRACKER")
