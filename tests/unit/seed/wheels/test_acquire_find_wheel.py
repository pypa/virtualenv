from __future__ import absolute_import, unicode_literals

import pytest

from virtualenv.seed.wheels.acquire import find_compatible_in_house
from virtualenv.seed.wheels.embed import BUNDLE_FOLDER, MAX, get_embed_wheel


def test_find_latest(for_py_version):
    result = find_compatible_in_house("setuptools", None, for_py_version, BUNDLE_FOLDER)
    expected = get_embed_wheel("setuptools", for_py_version)
    assert result.path == expected.path


def test_find_exact(for_py_version):
    expected = get_embed_wheel("setuptools", for_py_version)
    result = find_compatible_in_house("setuptools", "=={}".format(expected.version), for_py_version, BUNDLE_FOLDER)
    assert result.path == expected.path


def test_find_less_than(for_py_version):
    latest = get_embed_wheel("setuptools", MAX)
    result = find_compatible_in_house("setuptools", "<{}".format(latest.version), MAX, BUNDLE_FOLDER)
    assert result is not None
    assert result.path != latest.path


def test_find_bad_spec(for_py_version):
    with pytest.raises(ValueError, match="bad"):
        find_compatible_in_house("setuptools", "bad", MAX, BUNDLE_FOLDER)
