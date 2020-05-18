from virtualenv.seed.wheels.embed import get_embed_wheel


def test_wheel_support_no_python_requires(mocker):
    wheel = get_embed_wheel("setuptools", for_py_version=None)
    zip_mock = mocker.MagicMock()
    mocker.patch("virtualenv.seed.wheels.util.ZipFile", new=zip_mock)
    zip_mock.return_value.__enter__.return_value.read = lambda name: b""

    supports = wheel.support_py("3.8")
    assert supports is True
