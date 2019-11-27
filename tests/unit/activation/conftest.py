from __future__ import absolute_import, unicode_literals

import os

import pytest
from pathlib2 import Path

from virtualenv.run import run_via_cli


@pytest.fixture(scope="session")
def activation_python(tmp_path_factory):
    path = tmp_path_factory.mktemp("activation-test-env")
    prev_cwd = os.getcwd()
    try:
        os.chdir(str(path))
        session = run_via_cli([str(path), "--seeder", "none"])
        pydoc_test = Path(session.creator.site_packages[0]) / "pydoc_test.py"
        pydoc_test.write_text('"""This is pydoc_test.py"""')
        yield session, pydoc_test
    finally:
        os.chdir(str(prev_cwd))
