from __future__ import annotations

import sys
from textwrap import dedent

import pytest

from virtualenv.info import IS_PYPY, IS_WIN, fs_supports_symlink
from virtualenv.run import session_via_cli


@pytest.mark.skipif(not fs_supports_symlink(), reason="symlink is not supported")
@pytest.mark.xfail(
    # https://doc.pypy.org/en/latest/install.html?highlight=symlink#download-a-pre-built-pypy
    IS_PYPY and IS_WIN and sys.version_info[0:2] >= (3, 9),
    reason="symlink is not supported",
)
def test_ini_can_be_overwritten_by_flag(tmp_path, monkeypatch):
    custom_ini = tmp_path / "conf.ini"
    custom_ini.write_text(
        dedent(
            """
        [virtualenv]
        copies = True
        """,
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("VIRTUALENV_CONFIG_FILE", str(custom_ini))

    result = session_via_cli(["venv", "--symlinks"])

    symlinks = result.creator.symlinks
    assert symlinks is True
