from __future__ import absolute_import, unicode_literals

import pytest

from virtualenv.activation import BashActivator


@pytest.mark.timeout(30)
def test_bash(raise_on_non_source_class, activation_tester):
    class Bash(raise_on_non_source_class):
        def __init__(self, session):
            super(Bash, self).__init__(
                BashActivator, session, "bash", "activate.sh", "sh", "You must source this script: $ source "
            )

    activation_tester(Bash)
