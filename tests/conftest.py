from __future__ import absolute_import, unicode_literals

import os
import subprocess

import pytest

import virtualenv


@pytest.fixture(scope="session")
def clean_python(tmp_path_factory):
    path = tmp_path_factory.mktemp("activation-test-env")
    prev_cwd = os.getcwd()
    try:
        os.chdir(str(path))
        home_dir, _, __, bin_dir = virtualenv.path_locations(str(path / "env"))
        virtualenv.create_environment(home_dir, no_pip=True, no_setuptools=True, no_wheel=True)

        site_packages = subprocess.check_output(
            [
                os.path.join(bin_dir, virtualenv.EXPECTED_EXE),
                "-c",
                "from distutils.sysconfig import get_python_lib; print(get_python_lib())",
            ],
            universal_newlines=True,
        ).strip()

        pydoc_test = path.__class__(site_packages) / "pydoc_test.py"
        pydoc_test.write_text('"""This is pydoc_test.py"""')
    finally:
        os.chdir(str(prev_cwd))

    yield home_dir, bin_dir, pydoc_test
