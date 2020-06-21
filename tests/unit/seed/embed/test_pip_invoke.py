from __future__ import absolute_import, unicode_literals

import itertools
import sys
from shutil import copy2

import pytest

from virtualenv.run import cli_run
from virtualenv.seed.embed.pip_invoke import PipInvoke
from virtualenv.seed.wheels.bundle import load_embed_wheel
from virtualenv.seed.wheels.embed import BUNDLE_FOLDER, BUNDLE_SUPPORT


@pytest.mark.slow
@pytest.mark.parametrize("no", ["pip", "setuptools", "wheel", ""])
def test_base_bootstrap_via_pip_invoke(tmp_path, coverage_env, mocker, current_fastest, no):
    extra_search_dir = tmp_path / "extra"
    extra_search_dir.mkdir()
    for_py_version = "{}.{}".format(*sys.version_info[0:2])
    new = BUNDLE_SUPPORT[for_py_version]
    for wheel_filename in BUNDLE_SUPPORT[for_py_version].values():
        copy2(str(BUNDLE_FOLDER / wheel_filename), str(extra_search_dir))

    def _load_embed_wheel(app_data, distribution, for_py_version, version):
        return load_embed_wheel(app_data, distribution, old_ver, version)

    old_ver = "3.4"
    old = BUNDLE_SUPPORT[old_ver]
    mocker.patch("virtualenv.seed.wheels.bundle.load_embed_wheel", side_effect=_load_embed_wheel)

    def _execute(cmd, env):
        expected = set()
        for distribution, with_version in versions.items():
            if distribution == no:
                continue
            if with_version == "embed":
                expected.add(BUNDLE_FOLDER)
            elif old[dist] != new[dist]:
                expected.add(extra_search_dir)
        expected_list = list(
            itertools.chain.from_iterable(["--find-links", str(e)] for e in sorted(expected, key=lambda x: str(x))),
        )
        found = cmd[-len(expected_list) :]
        assert "--no-index" not in cmd
        cmd.append("--no-index")
        assert found == expected_list
        return original(cmd, env)

    original = PipInvoke._execute
    run = mocker.patch.object(PipInvoke, "_execute", side_effect=_execute)
    versions = {"pip": "embed", "setuptools": "bundle", "wheel": new["wheel"].split("-")[1]}

    create_cmd = [
        "--seeder",
        "pip",
        str(tmp_path / "env"),
        "--download",
        "--creator",
        current_fastest,
        "--extra-search-dir",
        str(extra_search_dir),
        "--app-data",
        str(tmp_path / "app-data"),
    ]
    for dist, version in versions.items():
        create_cmd.extend(["--{}".format(dist), version])
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
