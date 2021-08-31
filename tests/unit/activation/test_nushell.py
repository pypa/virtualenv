from __future__ import absolute_import, unicode_literals

import pytest

from virtualenv.activation import NushellActivator
from virtualenv.info import IS_WIN


@pytest.mark.skipif(IS_WIN, reason="Github Actions ships with WSL bash")
def test_nushell(activation_tester_class, activation_tester):
    class Nushell(activation_tester_class):
        def __init__(self, session):
            super(Nushell, self).__init__(NushellActivator, session, "nu", "activate.nu", "nu")

    activation_tester(Nushell)
