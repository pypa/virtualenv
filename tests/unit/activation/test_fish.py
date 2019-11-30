from __future__ import absolute_import, unicode_literals


def test_csh(activation_tester_class, activation_tester):
    class Fish(activation_tester_class):
        def __init__(self, session):
            super(Fish, self).__init__(session, "fish", "activate.fish", "fish")

    activation_tester(Fish)
