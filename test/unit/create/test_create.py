from __future__ import absolute_import, unicode_literals

import os
import stat
import sys

import pytest
import six
from pathlib2 import Path

from virtualenv.__main__ import run
from virtualenv.interpreters.create.api import DEBUG_SCRIPT, get_env_debug_info
from virtualenv.interpreters.discovery import CURRENT
from virtualenv.run import run_via_cli

SYSTEM = get_env_debug_info(CURRENT.system_executable, DEBUG_SCRIPT)


def cleanup_sys_path(path):
    from virtualenv.interpreters.create.api import HERE

    path = [Path(i).absolute() for i in path]
    to_remove = [Path(HERE)]
    if str("PYCHARM_HELPERS_DIR") in os.environ:
        to_remove.append(Path(os.environ[str("PYCHARM_HELPERS_DIR")]).parent / "pydev")
    for elem in to_remove:
        try:
            index = path.index(elem)
            del path[index]
        except ValueError:
            pass
    return path


@pytest.mark.parametrize("global_access", [False, True], ids=["no_global", "ok_global"])
@pytest.mark.parametrize(
    "use_venv", [False, True] if six.PY3 else [False], ids=["no_venv", "venv"] if six.PY3 else ["no_venv"]
)
def test_create_no_seed(python, use_venv, global_access, tmp_path, enable_coverage_in_virtual_env):
    cmd = ["-v", "-v", "-p", str(python), str(tmp_path), "--without-pip"]
    if global_access:
        cmd.append("--system-site-packages")
    if not use_venv:
        cmd.append("--no-venv")
    result = run_via_cli(cmd)
    for site_package in result.site_packages:
        content = list(site_package.iterdir())
        assert not content, "\n".join(str(i) for i in content)
    assert result.env_name == tmp_path.name
    sys_path = cleanup_sys_path(result.debug["sys"]["path"])
    system_sys_path = cleanup_sys_path(SYSTEM["sys"]["path"])
    our_paths = set(sys_path) - set(system_sys_path)
    our_paths_repr = "\n".join(repr(i) for i in our_paths)

    # ensure we have at least one extra path added
    assert len(our_paths) >= 1, our_paths_repr
    # ensure all additional paths are related to the virtual environment
    for path in our_paths:
        assert str(path).startswith(str(tmp_path)), path
    # ensure there's at least a site-packages folder as part of the virtual environment added
    assert any(p for p in our_paths if p.parts[-1] == "site-packages"), our_paths_repr

    # ensure the global site package is added or not, depending on flag
    last_from_system_path = next(i for i in reversed(system_sys_path) if str(i).startswith(SYSTEM["sys"]["prefix"]))
    if global_access:
        common = []
        for left, right in zip(reversed(system_sys_path), reversed(sys_path)):
            if left == right:
                common.append(left)
            else:
                break
        assert len(common)
    else:
        assert last_from_system_path not in sys_path


@pytest.mark.skipif(not CURRENT.has_venv, reason="requires venv interpreter")
def test_venv_fails(tmp_path, capsys):
    before = tmp_path.stat().st_mode
    cfg_path = tmp_path / "pyvenv.cfg"
    cfg_path.write_text(six.ensure_text(""))
    cfg = str(cfg_path)
    try:
        os.chmod(cfg, stat.S_IREAD | stat.S_IRGRP | stat.S_IROTH)
        cmd = ["-p", str(CURRENT.executable), str(tmp_path), "--without-pip"]
        with pytest.raises(SystemExit) as context:
            run(cmd)
        assert context.value.code != 0
    finally:
        os.chmod(cfg, before)
    out, err = capsys.readouterr()
    assert "subprocess call failed for" in out, out
    assert "Error:" in err, err


@pytest.mark.skipif(not sys.version_info[0] == 2, reason="python 2 only test")
def test_debug_bad_virtualenv(tmp_path):
    cmd = [str(tmp_path), "--without-pip"]
    result = run_via_cli(cmd)
    # if the site.py is removed/altered the debug should fail as no one is around to fix the paths
    site_py = result.lib_dir / "site.py"
    site_py.unlink()
    # insert something that writes something on the stdout
    site_py.write_text('import sys; sys.stdout.write(repr("std-out")); sys.stderr.write("std-err"); raise ValueError')
    debug_info = result.debug
    assert debug_info["returncode"]
    assert debug_info["err"].startswith("std-err")
    assert debug_info["out"] == "'std-out'"
    assert debug_info["exception"]


@pytest.mark.parametrize(
    "use_venv", [False, True] if six.PY3 else [False], ids=["no_venv", "venv"] if six.PY3 else ["no_venv"]
)
@pytest.mark.parametrize("clear", [True, False], ids=["clear", "no_clear"])
def test_create_clear_resets(tmp_path, use_venv, clear):
    marker = tmp_path / "magic"
    cmd = [str(tmp_path), "--without-pip"]
    if not use_venv:
        cmd.append("--no-venv")

    run_via_cli(cmd)

    marker.write_text("")  # if we a marker file this should be gone on a clear run, remain otherwise
    assert marker.exists()

    run_via_cli(cmd + (["--clear"] if clear else []))
    assert marker.exists() is not clear


@pytest.mark.parametrize(
    "use_venv", [False, True] if six.PY3 else [False], ids=["no_venv", "venv"] if six.PY3 else ["no_venv"]
)
@pytest.mark.parametrize("prompt", [None, "magic"])
def test_prompt_set(tmp_path, use_venv, prompt):
    cmd = [str(tmp_path), "--without-pip"]
    if prompt is not None:
        cmd.extend(["--prompt", "magic"])
    if not use_venv:
        cmd.append("--no-venv")

    result = run_via_cli(cmd)
    assert result.prompt == (tmp_path.name if prompt is None else prompt)
    env = result.pyvenv_path.read_text()
    if prompt is None:
        assert "prompt = " not in env
    else:
        if use_venv is False:
            prompt_line = "prompt = {}".format(prompt)
            assert prompt_line in env
