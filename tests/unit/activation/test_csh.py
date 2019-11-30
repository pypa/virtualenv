from __future__ import absolute_import, unicode_literals

from virtualenv.activation import CShellActivator


def test_csh(activation_tester_class, activation_tester):
    class Csh(activation_tester_class):
        def __init__(self, session):
            super(Csh, self).__init__(CShellActivator, session, "csh", "activate.csh", "csh")

    activation_tester(Csh)
