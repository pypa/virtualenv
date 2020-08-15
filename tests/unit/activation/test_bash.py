from __future__ import absolute_import, unicode_literals

import pytest

from virtualenv.activation import BashActivator
from virtualenv.activation.via_template import ViaTemplateActivator
from virtualenv.info import IS_WIN
from virtualenv.util.path import Path
from virtualenv.util.six import ensure_text


@pytest.mark.skipif(IS_WIN, reason="Github Actions ships with WSL bash")
def test_bash(raise_on_non_source_class, activation_tester):
    class Bash(raise_on_non_source_class):
        def __init__(self, session):
            super(Bash, self).__init__(
                BashActivator, session, "bash", "activate", "sh", "You must source this script: $ source ",
            )

    activation_tester(Bash)


@pytest.mark.skipif(not IS_WIN, reason="Only makes sense on Windows")
def test_bash_activate_script_has_unix_line_endings(tmpdir, mocker):
    class Mock_ViaTemplateActivator(ViaTemplateActivator):
        def generate(self, creator):
            file_path = ensure_text(str(tmpdir / "activate"))
            with open(file_path, "wb") as windows_line_endings_file:
                windows_line_endings_file.writelines([b"Test_file\r\n"] * 10)

            return [Path(file_path)]

    class TestBashActivator(BashActivator, Mock_ViaTemplateActivator):
        pass

    (file_path,) = TestBashActivator(mocker.MagicMock()).generate(mocker.MagicMock())
    assert b"Test_file\n" * 10 == file_path.read_bytes()
