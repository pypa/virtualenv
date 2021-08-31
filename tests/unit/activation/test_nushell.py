from __future__ import absolute_import, unicode_literals

from virtualenv.activation import NushellActivator
from virtualenv.info import IS_WIN


def test_nushell(activation_tester_class, activation_tester):
    class Nushell(activation_tester_class):
        def __init__(self, session):
            super(Nushell, self).__init__(NushellActivator, session, "nu", "activate.nu", "nu")

    activation_tester(Nushell)
