from __future__ import absolute_import, unicode_literals

import pytest

from virtualenv.activation import NushellActivator, nushell
from virtualenv.info import IS_WIN


@pytest.mark.skipif(IS_WIN, reason="Github Actions ships with WSL bash")
def test_nushell(activation_tester_class, activation_tester):
    class Nushell(activation_tester_class):
        def __init__(self, session):
            super(Nushell, self).__init__(NushellActivator, session, "nu", "activate.nu", "nu")
            self.activate_cmd = "source"

            deactivate = session.creator.dest / session.creator.bin_dir / "deactivate.nu"
            self.deactivate = "source '{}'".format(deactivate)

    activation_tester(Nushell)
