from __future__ import absolute_import, unicode_literals

import pytest

from virtualenv.discovery.py_info import PythonInfo
from virtualenv.run import cli_run
from virtualenv.seed.embed.pip_invoke import PipInvoke
from virtualenv.seed.embed.wheels import BUNDLE_SUPPORT
from virtualenv.seed.embed.wheels.acquire import BUNDLE_FOLDER


@pytest.mark.slow
@pytest.mark.parametrize("no", ["pip", "setuptools", "wheel", ""])
def test_base_bootstrap_via_pip_invoke(tmp_path, coverage_env, mocker, current_fastest, no):
    bundle_ver = BUNDLE_SUPPORT[PythonInfo.current_system().version_release_str]

    extra_search_dir = tmp_path / "extra"
    extra_search_dir.mkdir()

    original = PipInvoke._execute

    def _execute(cmd, env):
        assert set(cmd[-4:]) == {"--find-links", str(extra_search_dir), str(BUNDLE_FOLDER)}
        return original(cmd, env)

    run = mocker.patch.object(PipInvoke, "_execute", side_effect=_execute)

    create_cmd = [
        "--seeder",
        "pip",
        str(tmp_path / "env"),
        "--download",
        "--pip",
        bundle_ver["pip"].split("-")[1],
        "--setuptools",
        bundle_ver["setuptools"].split("-")[1],
        "--creator",
        current_fastest,
        "--extra-search-dir",
        str(extra_search_dir),
    ]
    if no:
        create_cmd.append("--no-{}".format(no))
    result = cli_run(create_cmd)
    coverage_env()

    assert result
    assert run.call_count == 1

    site_package = result.creator.purelib
    pip = site_package / "pip"
    setuptools = site_package / "setuptools"
    wheel = site_package / "wheel"
    files_post_first_create = list(site_package.iterdir())

    if no:
        no_file = locals()[no]
        assert no not in files_post_first_create

    for key in ("pip", "setuptools", "wheel"):
        if key == no:
            continue
        assert locals()[key] in files_post_first_create
