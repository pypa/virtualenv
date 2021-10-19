from __future__ import absolute_import, unicode_literals

from argparse import Namespace

import pytest

from virtualenv.activation.activator import Activator


class FakeActivator(Activator):
    def generate(self, creator):
        raise NotImplementedError


@pytest.mark.parametrize(
    ("prompt", "expected"),
    (
        (None, None),
        ("foo", "foo"),
        # Special case for the current directory
        (".", "(virtualenv) "),
    ),
)
def test_activator_prompt_normal(prompt, expected):
    activator = FakeActivator(Namespace(prompt=prompt))
    assert activator.flag_prompt == expected
