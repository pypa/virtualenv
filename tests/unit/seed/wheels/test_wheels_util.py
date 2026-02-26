from __future__ import annotations

import pytest

from virtualenv.seed.wheels.embed import MAX, get_embed_wheel
from virtualenv.seed.wheels.util import Wheel


def test_wheel_support_no_python_requires(mocker) -> None:
    wheel = get_embed_wheel("setuptools", for_py_version=None)
    zip_mock = mocker.MagicMock()
    mocker.patch("virtualenv.seed.wheels.util.ZipFile", new=zip_mock)
    zip_mock.return_value.__enter__.return_value.read = lambda _name: b""

    supports = wheel.support_py("3.8")
    assert supports is True


def test_bad_as_version_tuple() -> None:
    with pytest.raises(ValueError, match="bad"):
        Wheel.as_version_tuple("bad")


def test_wheel_not_support() -> None:
    wheel = get_embed_wheel("setuptools", MAX)
    assert wheel.support_py("3.3") is False


def test_wheel_repr() -> None:
    wheel = get_embed_wheel("setuptools", MAX)
    assert str(wheel.path) in repr(wheel)


def test_unknown_distribution() -> None:
    wheel = get_embed_wheel("unknown", MAX)
    assert wheel is None
