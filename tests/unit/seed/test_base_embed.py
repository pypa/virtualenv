import pytest

from virtualenv.run import session_via_cli


@pytest.mark.parametrize(
    "args, download", [([], False), (["--no-download"], False), (["--never-download"], False), (["--download"], True)],
)
def test_download_cli_flag(args, download, tmp_path):
    session = session_via_cli(args + [str(tmp_path)])
    assert session.seeder.download is download
