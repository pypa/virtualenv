from virtualenv.seed.embed.wheels.acquire import get_bundled_wheel, wheel_support_py


def test_wheel_support_no_python_requires(mocker):
    wheel = get_bundled_wheel(package="setuptools", version_release=None)
    zip_mock = mocker.MagicMock()
    mocker.patch("virtualenv.seed.embed.wheels.acquire.ZipFile", new=zip_mock)
    zip_mock.return_value.__enter__.return_value.read = lambda name: b""

    supports = wheel_support_py(wheel, "3.8")
    assert supports is True
