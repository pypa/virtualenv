import pytest

from virtualenv.seed.ensurepip.ensurepip import EnsurePipSeeder


def _mock_p_open(mocker, returncode):
    instance = mocker.MagicMock(returncode=returncode)
    return mocker.patch("virtualenv.seed.ensurepip.ensurepip.Popen", return_value=instance)


def test_ensurepip(mocker):
    p_open = _mock_p_open(mocker, 0)
    seeder = EnsurePipSeeder(mocker.MagicMock(no_seed=False))
    seeder.run(mocker.MagicMock(exe="python-creator-exe"))
    p_open.assert_called_once_with(["python-creator-exe", "-m", "ensurepip"])


def test_ensurepip_failed(mocker):
    _mock_p_open(mocker, 1)
    seeder = EnsurePipSeeder(mocker.MagicMock(no_seed=False))
    with pytest.raises(RuntimeError):
        seeder.run(mocker.MagicMock(exe="python-creator-exe"))


def test_ensurepip_sets_enabled(mocker):
    assert EnsurePipSeeder(mocker.MagicMock(no_seed=False)).enabled
    assert not EnsurePipSeeder(mocker.MagicMock(no_seed=True)).enabled
