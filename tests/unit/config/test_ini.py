from textwrap import dedent

import pytest

from virtualenv.info import fs_supports_symlink
from virtualenv.run import session_via_cli


@pytest.mark.skipif(not fs_supports_symlink(), reason="symlink is not supported")
def test_ini_can_be_overwritten_by_flag(tmp_path, monkeypatch):
    custom_ini = tmp_path / "conf.ini"
    custom_ini.write_text(
        dedent(
            """
        [virtualenv]
        copies = True
        """,
        ),
    )
    monkeypatch.setenv("VIRTUALENV_CONFIG_FILE", str(custom_ini))

    result = session_via_cli(["venv", "--symlinks"])

    symlinks = result.creator.symlinks
    assert symlinks is True
