from __future__ import absolute_import, unicode_literals

import sys

from virtualenv import cli_run
from virtualenv.util.six import ensure_text
from virtualenv.util.subprocess import run_cmd


def test_app_data_pinning(tmp_path):
    version = "19.1.1" if sys.version_info[0:2] == (3, 4) else "19.3.1"
    result = cli_run([ensure_text(str(tmp_path)), "--pip", version, "--activators", "", "--seeder", "app-data"])
    code, out, err = run_cmd([str(result.creator.script("pip")), "list", "--disable-pip-version-check"])
    assert not code
    assert not err
    for line in out.splitlines():
        parts = line.split()
        if parts and parts[0] == "pip":
            assert parts[1] == version
            break
    else:
        assert not out
