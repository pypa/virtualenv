from __future__ import absolute_import, unicode_literals

import difflib
import os
import stat
import sys

import pytest
import six

from virtualenv.__main__ import run
from virtualenv.interpreters.create.creator import DEBUG_SCRIPT, get_env_debug_info
from virtualenv.interpreters.discovery.builtin import get_interpreter
from virtualenv.interpreters.discovery.py_info import CURRENT, PythonInfo
from virtualenv.pyenv_cfg import PyEnvCfg
from virtualenv.run import run_via_cli, session_via_cli
from virtualenv.util import Path


def test_os_path_sep_not_allowed(tmp_path, capsys):
    target = str(tmp_path / "a{}b".format(os.pathsep))
    err = _non_success_exit_code(capsys, target)
    msg = (
        "destination {!r} must not contain the path separator ({}) as this"
        " would break the activation scripts".format(target, os.pathsep)
    )
    assert msg in err, err


def _non_success_exit_code(capsys, target):
    with pytest.raises(SystemExit) as context:
        run_via_cli(args=[target])
    assert context.value.code != 0
    out, err = capsys.readouterr()
    assert not out, out
    return err


def test_destination_exists_file(tmp_path, capsys):
    target = tmp_path / "out"
    target.write_text("")
    err = _non_success_exit_code(capsys, str(target))
    msg = "the destination {} already exists and is a file".format(str(target))
    assert msg in err, err


@pytest.mark.skipif(sys.platform == "win32", reason="no chmod on Windows")
def test_destination_not_write_able(tmp_path, capsys):
    target = tmp_path
    prev_mod = target.stat().st_mode
    target.chmod(0o444)
    try:
        err = _non_success_exit_code(capsys, str(target))
        msg = "the destination . is not write-able at {}".format(str(target))
        assert msg in err, err
    finally:
        target.chmod(prev_mod)


SYSTEM = get_env_debug_info(Path(CURRENT.system_executable), DEBUG_SCRIPT)


def cleanup_sys_path(paths):
    from virtualenv.interpreters.create.creator import HERE

    paths = [Path(i).absolute() for i in paths]
    to_remove = [Path(HERE)]
    if str("PYCHARM_HELPERS_DIR") in os.environ:
        to_remove.append(Path(os.environ[str("PYCHARM_HELPERS_DIR")]).parent)
        to_remove.append(Path(os.path.expanduser("~")) / ".PyCharm")
    result = [i for i in paths if not any(str(i).startswith(str(t)) for t in to_remove)]
    return result


@pytest.mark.parametrize("global_access", [False, True], ids=["no_global", "ok_global"])
@pytest.mark.parametrize(
    "use_venv", [False, True] if six.PY3 else [False], ids=["no_venv", "venv"] if six.PY3 else ["no_venv"]
)
def test_create_no_seed(python, use_venv, global_access, tmp_path, coverage_env, special_name_dir):
    dest = special_name_dir
    cmd = ["-v", "-v", "-p", six.ensure_text(python), six.ensure_text(str(dest)), "--without-pip", "--activators", ""]
    if global_access:
        cmd.append("--system-site-packages")
    if use_venv:
        cmd.extend(["--creator", "venv"])
    result = run_via_cli(cmd)
    coverage_env()
    for site_package in result.creator.site_packages:
        content = list(site_package.iterdir())
        assert not content, "\n".join(str(i) for i in content)
    assert result.creator.env_name == six.ensure_text(dest.name)
    debug = result.creator.debug
    sys_path = cleanup_sys_path(debug["sys"]["path"])
    system_sys_path = cleanup_sys_path(SYSTEM["sys"]["path"])
    our_paths = set(sys_path) - set(system_sys_path)
    our_paths_repr = "\n".join(six.ensure_text(repr(i)) for i in our_paths)

    # ensure we have at least one extra path added
    assert len(our_paths) >= 1, our_paths_repr
    # ensure all additional paths are related to the virtual environment
    for path in our_paths:
        assert str(path).startswith(str(dest)), "{} does not start with {}".format(
            six.ensure_text(str(path)), six.ensure_text(str(dest))
        )
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

        def list_to_str(iterable):
            return [six.ensure_text(str(i)) for i in iterable]

        assert common, "\n".join(difflib.unified_diff(list_to_str(sys_path), list_to_str(system_sys_path)))
    else:
        assert last_from_system_path not in sys_path


@pytest.mark.skipif(not CURRENT.has_venv, reason="requires venv interpreter")
def test_venv_fails_not_inline(tmp_path, capsys, mocker):
    def _session_via_cli(args):
        session = session_via_cli(args)
        assert session.creator.can_be_inline is False
        return session

    mocker.patch("virtualenv.run.session_via_cli", side_effect=_session_via_cli)
    before = tmp_path.stat().st_mode
    cfg_path = tmp_path / "pyvenv.cfg"
    cfg_path.write_text(six.ensure_text(""))
    cfg = str(cfg_path)
    try:
        os.chmod(cfg, stat.S_IREAD | stat.S_IRGRP | stat.S_IROTH)
        cmd = ["-p", str(CURRENT.executable), str(tmp_path), "--without-pip", "--creator", "venv"]
        with pytest.raises(SystemExit) as context:
            run(cmd)
        assert context.value.code != 0
    finally:
        os.chmod(cfg, before)
    out, err = capsys.readouterr()
    assert "subprocess call failed for" in out, out
    assert "Error:" in err, err


@pytest.mark.skipif(not sys.version_info[0] == 2, reason="python 2 only tests")
def test_debug_bad_virtualenv(tmp_path):
    cmd = [str(tmp_path), "--without-pip"]
    result = run_via_cli(cmd)
    # if the site.py is removed/altered the debug should fail as no one is around to fix the paths
    site_py = result.creator.lib_dir / "site.py"
    site_py.unlink()
    # insert something that writes something on the stdout
    site_py.write_text('import sys; sys.stdout.write(repr("std-out")); sys.stderr.write("std-err"); raise ValueError')
    debug_info = result.creator.debug
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
    cmd = [str(tmp_path), "--seeder", "none"]
    if use_venv:
        cmd.extend(["--creator", "venv"])
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
    cmd = [str(tmp_path), "--seeder", "none"]
    if prompt is not None:
        cmd.extend(["--prompt", "magic"])
    if not use_venv and six.PY3:
        cmd.extend(["--creator", "venv"])

    result = run_via_cli(cmd)
    actual_prompt = tmp_path.name if prompt is None else prompt
    cfg = PyEnvCfg.from_file(result.creator.pyenv_cfg.path)
    if prompt is None:
        assert "prompt" not in cfg
    else:
        if use_venv is False:
            assert "prompt" in cfg, list(cfg.content.keys())
            assert cfg["prompt"] == actual_prompt


@pytest.fixture(scope="session")
def cross_python(is_inside_ci):
    spec = "{}{}".format(CURRENT.implementation, 2 if CURRENT.version_info.major == 3 else 3)
    interpreter = get_interpreter(spec)
    if interpreter is None:
        msg = "could not find {}".format(spec)
        if is_inside_ci:
            raise RuntimeError(msg)
        pytest.skip(msg=msg)
    yield interpreter


def test_cross_major(cross_python, coverage_env, tmp_path):
    cmd = [
        "-v",
        "-v",
        "-p",
        six.ensure_text(cross_python.executable),
        six.ensure_text(str(tmp_path)),
        "--seeder",
        "none",
        "--activators",
        "",
    ]
    result = run_via_cli(cmd)
    coverage_env()
    env = PythonInfo.from_exe(str(result.creator.exe))
    assert env.version_info.major != CURRENT.version_info.major
