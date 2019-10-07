from __future__ import absolute_import, unicode_literals

import os
import subprocess
import sys

from virtualenv.interpreters.discovery import CURRENT
from virtualenv.run import run_via_cli
from virtualenv.seed.wheels import BUNDLE_SUPPORT


def test_base_bootstrap_link_via_app_data(tmp_path):
    bundle_ver = BUNDLE_SUPPORT[CURRENT.version_release_str]
    create_cmd = [
        str(tmp_path / "env"),
        "--no-venv",
        "--download",
        "--pip",
        bundle_ver["pip"].split("-")[1],
        "--setuptools",
        bundle_ver["setuptools"].split("-")[1],
    ]
    result = run_via_cli(create_cmd)
    assert result

    # uninstalling pip/setuptools now should leave us with a clean env
    site_package = result.site_packages[0]
    pip = site_package / "pip"
    setuptools = site_package / "setuptools"

    files_post_first_create = list(site_package.iterdir())
    assert pip in files_post_first_create
    assert setuptools in files_post_first_create

    remove_cmd = [
        str(result.env_exe),
        "-m",
        "pip",
        "--verbose",
        "--disable-pip-version-check",
        "uninstall",
        "-y",
        "setuptools",
    ]
    assert not subprocess.check_call(remove_cmd)
    assert site_package.exists()

    files_post_first_uninstall = list(site_package.iterdir())
    assert pip in files_post_first_uninstall
    assert setuptools not in files_post_first_uninstall

    # check we can run it again and will work - checks both overwrite and reuse cache
    result = run_via_cli(create_cmd)
    assert result
    files_post_second_create = list(site_package.iterdir())
    assert files_post_first_create == files_post_second_create

    assert not subprocess.check_call(remove_cmd + ["pip"])
    # pip is greedy here, removing all packages removes the site-package too
    if site_package.exists():
        post_run = list(site_package.iterdir())
        assert not post_run, "\n".join(str(i) for i in post_run)

    if sys.version_info[0:2] == (3, 4) and "PIP_REQ_TRACKER" in os.environ:
        os.environ.pop("PIP_REQ_TRACKER")
