from virtualenv.seed.embed.wheels.acquire import get_bundled_wheel


def test_wheel_support_no_python_requires(mocker):
    wheel = get_bundled_wheel("setuptools", for_py_version=None)
    zip_mock = mocker.MagicMock()
    mocker.patch("virtualenv.seed.embed.wheels.util.ZipFile", new=zip_mock)
    zip_mock.return_value.__enter__.return_value.read = lambda name: b""

    supports = wheel.support_py("3.8")
    assert supports is True
