from __future__ import absolute_import, unicode_literals

import pytest

from virtualenv.discovery.py_info import PythonInfo
from virtualenv.run import cli_run
from virtualenv.seed.embed.wheels import BUNDLE_SUPPORT


@pytest.mark.slow
def test_base_bootstrap_via_pip_invoke(tmp_path, coverage_env, current_fastest):
    bundle_ver = BUNDLE_SUPPORT[PythonInfo.current_system().version_release_str]
    create_cmd = [
        "--seeder",
        "pip",
        str(tmp_path / "env"),
        "--download",
        "--pip",
        bundle_ver["pip"].split("-")[1],
        "--setuptools",
        bundle_ver["setuptools"].split("-")[1],
        "--creator",
        current_fastest,
    ]
    result = cli_run(create_cmd)
    coverage_env()
    assert result

    site_package = result.creator.purelib
    pip = site_package / "pip"
    setuptools = site_package / "setuptools"
    wheel = site_package / "wheel"

    files_post_first_create = list(site_package.iterdir())
    assert pip in files_post_first_create
    assert setuptools in files_post_first_create
    assert wheel in files_post_first_create
