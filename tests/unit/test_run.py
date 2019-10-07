import pytest

from virtualenv.run import run_via_cli


def test_help(capsys):
    with pytest.raises(SystemExit) as context:
        run_via_cli(args=["-h"])
    assert context.value.code == 0

    out, err = capsys.readouterr()
    assert not err
    assert out
