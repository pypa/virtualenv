from __future__ import absolute_import, unicode_literals

from virtualenv import cli_run
from virtualenv.util.six import ensure_text
from virtualenv.util.subprocess import run_cmd


def test_app_data_pinning(tmp_path):
    result = cli_run([ensure_text(str(tmp_path)), "--pip", "19.3.1", "--activators", "", "--seeder", "app-data"])
    code, out, err = run_cmd([str(result.creator.script("pip")), "list", "--disable-pip-version-check"])
    assert not code
    assert not err
    for line in out.splitlines():
        parts = line.split()
        if parts and parts[0] == "pip":
            assert parts[1] == "19.3.1"
            break
    else:
        assert not out
