from __future__ import absolute_import, unicode_literals

import ast
import difflib
import gc
import json
import logging
import os
import shutil
import site
import stat
import subprocess
import sys
import zipfile
from collections import OrderedDict
from itertools import product
from stat import S_IREAD, S_IRGRP, S_IROTH
from textwrap import dedent
from threading import Thread

import pytest

from virtualenv.__main__ import run, run_with_catch
from virtualenv.create.creator import DEBUG_SCRIPT, Creator, get_env_debug_info
from virtualenv.create.pyenv_cfg import PyEnvCfg
from virtualenv.create.via_global_ref.builtin.cpython.cpython2 import CPython2PosixBase
from virtualenv.create.via_global_ref.builtin.cpython.cpython3 import CPython3Posix
from virtualenv.create.via_global_ref.builtin.python2.python2 import Python2
from virtualenv.discovery.py_info import PythonInfo
from virtualenv.info import IS_PYPY, IS_WIN, PY2, PY3, fs_is_case_sensitive
from virtualenv.run import cli_run, session_via_cli
from virtualenv.util.path import Path
from virtualenv.util.six import ensure_str, ensure_text

CURRENT = PythonInfo.current_system()


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
        run_with_catch(args=[target])
    assert context.value.code != 0
    out, err = capsys.readouterr()
    assert "SystemExit: " in out
    return err


def test_destination_exists_file(tmp_path, capsys):
    target = tmp_path / "out"
    target.write_text("")
    err = _non_success_exit_code(capsys, str(target))
    msg = "the destination {} already exists and is a file".format(str(target))
    assert msg in err, err


@pytest.mark.skipif(sys.platform == "win32", reason="Windows only applies R/O to files")
def test_destination_not_write_able(tmp_path, capsys):
    if hasattr(os, "geteuid"):
        if os.geteuid() == 0:
            pytest.skip("no way to check permission restriction when running under root")

    target = tmp_path
    prev_mod = target.stat().st_mode
    target.chmod(S_IREAD | S_IRGRP | S_IROTH)
    try:
        err = _non_success_exit_code(capsys, str(target))
        msg = "the destination . is not write-able at {}".format(str(target))
        assert msg in err, err
    finally:
        target.chmod(prev_mod)


def cleanup_sys_path(paths):
    from virtualenv.create.creator import HERE

    paths = [p.resolve() for p in (Path(os.path.abspath(i)) for i in paths) if p.exists()]
    to_remove = [Path(HERE)]
    if os.environ.get(str("PYCHARM_HELPERS_DIR")):
        to_remove.append(Path(os.environ[str("PYCHARM_HELPERS_DIR")]).parent)
        to_remove.append(Path(os.path.expanduser("~")) / ".PyCharm")
    result = [i for i in paths if not any(str(i).startswith(str(t)) for t in to_remove)]
    return result


@pytest.fixture(scope="session")
def system(session_app_data):
    return get_env_debug_info(Path(CURRENT.system_executable), DEBUG_SCRIPT, session_app_data, os.environ)


CURRENT_CREATORS = list(i for i in CURRENT.creators().key_to_class.keys() if i != "builtin")
CREATE_METHODS = []
for k, v in CURRENT.creators().key_to_meta.items():
    if k in CURRENT_CREATORS:
        if v.can_copy:
            CREATE_METHODS.append((k, "copies"))
        if v.can_symlink:
            CREATE_METHODS.append((k, "symlinks"))
_VENV_BUG_ON = (
    IS_PYPY
    and CURRENT.version_info[0:3] == (3, 6, 9)
    and CURRENT.pypy_version_info[0:2] == [7, 3, 0]
    and CURRENT.platform == "linux"
)


@pytest.mark.parametrize(
    "creator, isolated",
    [
        pytest.param(
            *i,
            marks=pytest.mark.xfail(
                reason="https://bitbucket.org/pypy/pypy/issues/3159/pypy36-730-venv-fails-with-copies-on-linux",
                strict=True,
            )
        )
        if _VENV_BUG_ON and i[0][0] == "venv" and i[0][1] == "copies"
        else i
        for i in product(CREATE_METHODS, ["isolated", "global"])
    ],
    ids=lambda i: "-".join(i) if isinstance(i, tuple) else i,
)
def test_create_no_seed(python, creator, isolated, system, coverage_env, special_name_dir):
    dest = special_name_dir
    creator_key, method = creator
    cmd = [
        "-v",
        "-v",
        "-p",
        ensure_text(python),
        ensure_text(str(dest)),
        "--without-pip",
        "--activators",
        "",
        "--creator",
        creator_key,
        "--{}".format(method),
    ]
    if isolated == "global":
        cmd.append("--system-site-packages")
    result = cli_run(cmd)
    creator = result.creator
    coverage_env()
    if IS_PYPY:
        # pypy cleans up file descriptors periodically so our (many) subprocess calls impact file descriptor limits
        # force a close of these on system where the limit is low-ish (e.g. MacOS 256)
        gc.collect()
    purelib = creator.purelib
    patch_files = {purelib / "{}.{}".format("_virtualenv", i) for i in ("py", "pyc", "pth")}
    patch_files.add(purelib / "__pycache__")
    content = set(creator.purelib.iterdir()) - patch_files
    assert not content, "\n".join(ensure_text(str(i)) for i in content)
    assert creator.env_name == ensure_text(dest.name)
    debug = creator.debug
    assert "exception" not in debug, "{}\n{}\n{}".format(debug.get("exception"), debug.get("out"), debug.get("err"))
    sys_path = cleanup_sys_path(debug["sys"]["path"])
    system_sys_path = cleanup_sys_path(system["sys"]["path"])
    our_paths = set(sys_path) - set(system_sys_path)
    our_paths_repr = "\n".join(ensure_text(repr(i)) for i in our_paths)

    # ensure we have at least one extra path added
    assert len(our_paths) >= 1, our_paths_repr
    # ensure all additional paths are related to the virtual environment
    for path in our_paths:
        msg = "\n{}\ndoes not start with {}\nhas:\n{}".format(
            ensure_text(str(path)),
            ensure_text(str(dest)),
            "\n".join(ensure_text(str(p)) for p in system_sys_path),
        )
        assert str(path).startswith(str(dest)), msg
    # ensure there's at least a site-packages folder as part of the virtual environment added
    assert any(p for p in our_paths if p.parts[-1] == "site-packages"), our_paths_repr

    # ensure the global site package is added or not, depending on flag
    global_sys_path = system_sys_path[-1]
    if isolated == "isolated":
        msg = "global sys path {} is in virtual environment sys path:\n{}".format(
            ensure_text(str(global_sys_path)),
            "\n".join(ensure_text(str(j)) for j in sys_path),
        )
        assert global_sys_path not in sys_path, msg
    else:
        common = []
        for left, right in zip(reversed(system_sys_path), reversed(sys_path)):
            if left == right:
                common.append(left)
            else:
                break

        def list_to_str(iterable):
            return [ensure_text(str(i)) for i in iterable]

        assert common, "\n".join(difflib.unified_diff(list_to_str(sys_path), list_to_str(system_sys_path)))

    # test that the python executables in the bin directory are either:
    # - files
    # - absolute symlinks outside of the venv
    # - relative symlinks inside of the venv
    if sys.platform == "win32":
        exes = ("python.exe",)
    else:
        exes = ("python", "python{}".format(*sys.version_info), "python{}.{}".format(*sys.version_info))
        if creator_key == "venv":
            # for venv some repackaging does not includes the pythonx.y
            exes = exes[:-1]
    for exe in exes:
        exe_path = creator.bin_dir / exe
        assert exe_path.exists(), "\n".join(str(i) for i in creator.bin_dir.iterdir())
        if not exe_path.is_symlink():  # option 1: a real file
            continue  # it was a file
        link = os.readlink(str(exe_path))
        if not os.path.isabs(link):  # option 2: a relative symlink
            continue
        # option 3: an absolute symlink, should point outside the venv
        assert not link.startswith(str(creator.dest))

    if IS_WIN and CURRENT.implementation == "CPython":
        python_w = creator.exe.parent / "pythonw.exe"
        assert python_w.exists()
        assert python_w.read_bytes() != creator.exe.read_bytes()

    if CPython3Posix.pyvenv_launch_patch_active(PythonInfo.from_exe(python)) and creator_key != "venv":
        result = subprocess.check_output(
            [str(creator.exe), "-c", 'import os; print(os.environ.get("__PYVENV_LAUNCHER__"))'],
            universal_newlines=True,
        ).strip()
        assert result == "None"

    if isinstance(creator, CPython2PosixBase):
        make_file = debug["makefile_filename"]
        assert os.path.exists(make_file)

    git_ignore = (dest / ".gitignore").read_text()
    assert git_ignore.splitlines() == ["# created by virtualenv automatically", "*"]


def test_create_vcs_ignore_exists(tmp_path):
    git_ignore = tmp_path / ".gitignore"
    git_ignore.write_text("magic")
    cli_run([str(tmp_path), "--without-pip", "--activators", ""])
    assert git_ignore.read_text() == "magic"


def test_create_vcs_ignore_override(tmp_path):
    git_ignore = tmp_path / ".gitignore"
    cli_run([str(tmp_path), "--without-pip", "--no-vcs-ignore", "--activators", ""])
    assert not git_ignore.exists()


def test_create_vcs_ignore_exists_override(tmp_path):
    git_ignore = tmp_path / ".gitignore"
    git_ignore.write_text("magic")
    cli_run([str(tmp_path), "--without-pip", "--no-vcs-ignore", "--activators", ""])
    assert git_ignore.read_text() == "magic"


@pytest.mark.skipif(not CURRENT.has_venv, reason="requires interpreter with venv")
def test_venv_fails_not_inline(tmp_path, capsys, mocker):
    if hasattr(os, "geteuid"):
        if os.geteuid() == 0:
            pytest.skip("no way to check permission restriction when running under root")

    def _session_via_cli(args, options=None, setup_logging=True, env=None):
        session = session_via_cli(args, options, setup_logging, env)
        assert session.creator.can_be_inline is False
        return session

    mocker.patch("virtualenv.run.session_via_cli", side_effect=_session_via_cli)
    before = tmp_path.stat().st_mode
    cfg_path = tmp_path / "pyvenv.cfg"
    cfg_path.write_text(ensure_text(""))
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
    result = cli_run(cmd)
    # if the site.py is removed/altered the debug should fail as no one is around to fix the paths
    site_py = result.creator.stdlib / "site.py"
    site_py.unlink()
    # insert something that writes something on the stdout
    site_py.write_text('import sys; sys.stdout.write(repr("std-out")); sys.stderr.write("std-err"); raise ValueError')
    debug_info = result.creator.debug
    assert debug_info["returncode"]
    assert debug_info["err"].startswith("std-err")
    assert "std-out" in debug_info["out"]
    assert debug_info["exception"]


@pytest.mark.parametrize("creator", CURRENT_CREATORS)
@pytest.mark.parametrize("clear", [True, False], ids=["clear", "no_clear"])
def test_create_clear_resets(tmp_path, creator, clear, caplog):
    caplog.set_level(logging.DEBUG)
    if creator == "venv" and clear is False:
        pytest.skip("venv without clear might fail")
    marker = tmp_path / "magic"
    cmd = [str(tmp_path), "--seeder", "app-data", "--without-pip", "--creator", creator, "-vvv"]
    cli_run(cmd)

    marker.write_text("")  # if we a marker file this should be gone on a clear run, remain otherwise
    assert marker.exists()

    cli_run(cmd + (["--clear"] if clear else []))
    assert marker.exists() is not clear


@pytest.mark.parametrize("creator", CURRENT_CREATORS)
@pytest.mark.parametrize("prompt", [None, "magic"])
def test_prompt_set(tmp_path, creator, prompt):
    cmd = [str(tmp_path), "--seeder", "app-data", "--without-pip", "--creator", creator]
    if prompt is not None:
        cmd.extend(["--prompt", "magic"])

    result = cli_run(cmd)
    actual_prompt = tmp_path.name if prompt is None else prompt
    cfg = PyEnvCfg.from_file(result.creator.pyenv_cfg.path)
    if prompt is None:
        assert "prompt" not in cfg
    else:
        if creator != "venv":
            assert "prompt" in cfg, list(cfg.content.keys())
            assert cfg["prompt"] == actual_prompt


@pytest.mark.slow
def test_cross_major(cross_python, coverage_env, tmp_path, session_app_data, current_fastest):
    cmd = [
        "-p",
        ensure_text(cross_python.executable),
        ensure_text(str(tmp_path)),
        "--no-setuptools",
        "--no-wheel",
        "--activators",
        "",
    ]
    result = cli_run(cmd)
    pip_scripts = {i.name.replace(".exe", "") for i in result.creator.script_dir.iterdir() if i.name.startswith("pip")}
    major, minor = cross_python.version_info[0:2]
    assert pip_scripts == {
        "pip",
        "pip{}".format(major),
        "pip-{}.{}".format(major, minor),
        "pip{}.{}".format(major, minor),
    }
    coverage_env()
    env = PythonInfo.from_exe(str(result.creator.exe), session_app_data)
    assert env.version_info.major != CURRENT.version_info.major


def test_create_parallel(tmp_path, monkeypatch, temp_app_data):
    def create(count):
        subprocess.check_call(
            [sys.executable, "-m", "virtualenv", "-vvv", str(tmp_path / "venv{}".format(count)), "--without-pip"],
        )

    threads = [Thread(target=create, args=(i,)) for i in range(1, 4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()


def test_creator_input_passed_is_abs(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = Creator.validate_dest("venv")
    assert str(result) == str(tmp_path / "venv")


@pytest.mark.skipif(os.altsep is None, reason="OS does not have an altsep")
def test_creator_replaces_altsep_in_dest(tmp_path):
    dest = str(tmp_path / "venv{}foobar")
    result = Creator.validate_dest(dest.format(os.altsep))
    assert str(result) == dest.format(os.sep)


def test_create_long_path(current_fastest, tmp_path):
    if sys.platform == "darwin":
        max_shebang_length = 512
    else:
        max_shebang_length = 127
    # filenames can be at most 255 long on macOS, so split to to levels
    count = max_shebang_length - len(str(tmp_path))
    folder = tmp_path / ("a" * (count // 2)) / ("b" * (count // 2)) / "c"
    folder.mkdir(parents=True)

    cmd = [str(folder)]
    result = cli_run(cmd)
    subprocess.check_call([str(result.creator.script("pip")), "--version"])


@pytest.mark.parametrize("creator", sorted(set(PythonInfo.current_system().creators().key_to_class) - {"builtin"}))
def test_create_distutils_cfg(creator, tmp_path, monkeypatch, session_app_data):
    result = cli_run([ensure_text(str(tmp_path / "venv")), "--activators", "", "--creator", creator])

    app = Path(__file__).parent / "console_app"
    dest = tmp_path / "console_app"
    shutil.copytree(str(app), str(dest))

    setup_cfg = dest / "setup.cfg"
    conf = dedent(
        """
            [install]
            prefix={0}{1}prefix
            install_purelib={0}{1}purelib
            install_platlib={0}{1}platlib
            install_headers={0}{1}headers
            install_scripts={0}{1}scripts
            install_data={0}{1}data
            """.format(
            tmp_path,
            os.sep,
        ),
    )
    setup_cfg.write_text(setup_cfg.read_text() + conf)

    monkeypatch.chdir(dest)  # distutils will read the setup.cfg from the cwd, so change to that

    install_demo_cmd = [
        str(result.creator.script("pip")),
        "--disable-pip-version-check",
        "install",
        str(dest),
        "--no-use-pep517",
        "-vv",
    ]
    subprocess.check_call(install_demo_cmd)

    magic = result.creator.script("magic")  # console scripts are created in the right location
    assert magic.exists()

    package_folder = result.creator.purelib / "demo"  # prefix is set to the virtualenv prefix for install
    assert package_folder.exists(), list_files(str(tmp_path))


def list_files(path):
    result = ""
    for root, _, files in os.walk(path):
        level = root.replace(path, "").count(os.sep)
        indent = " " * 4 * level
        result += "{}{}/\n".format(indent, os.path.basename(root))
        sub = " " * 4 * (level + 1)
        for f in files:
            result += "{}{}\n".format(sub, f)
    return result


@pytest.mark.parametrize("python_path_on", [True, False], ids=["on", "off"])
@pytest.mark.skipif(PY3, reason="we rewrite sys.path only on PY2")
def test_python_path(monkeypatch, tmp_path, python_path_on):
    result = cli_run([ensure_text(str(tmp_path)), "--without-pip", "--activators", ""])
    monkeypatch.chdir(tmp_path)
    case_sensitive = fs_is_case_sensitive()

    def _get_sys_path(flag=None):
        cmd = [str(result.creator.exe)]
        if flag:
            cmd.append(flag)
        cmd.extend(["-c", "import json; import sys; print(json.dumps(sys.path))"])
        return [i if case_sensitive else i.lower() for i in json.loads(subprocess.check_output(cmd))]

    monkeypatch.delenv(str("PYTHONPATH"), raising=False)
    base = _get_sys_path()

    # note the value result.creator.interpreter.system_stdlib cannot be set, as that would disable our custom site.py
    python_paths = [
        str(Path(result.creator.interpreter.prefix)),
        str(Path(result.creator.interpreter.system_stdlib) / "b"),
        str(result.creator.purelib / "a"),
        str(result.creator.purelib),
        str(result.creator.bin_dir),
        str(tmp_path / "base"),
        str(tmp_path / "base_sep") + os.sep,
        "name",
        "name{}".format(os.sep),
        str(tmp_path.parent / (ensure_text(tmp_path.name) + "_suffix")),
        ".",
        "..",
        "",
    ]
    python_path_env = os.pathsep.join(ensure_str(i) for i in python_paths)
    monkeypatch.setenv(str("PYTHONPATH"), python_path_env)

    extra_all = _get_sys_path(None if python_path_on else "-E")
    if python_path_on:
        assert extra_all[0] == ""  # the cwd is always injected at start as ''
        extra_all = extra_all[1:]
        assert base[0] == ""
        base = base[1:]

        assert not (set(base) - set(extra_all))  # all base paths are present
        abs_python_paths = list(OrderedDict((os.path.abspath(ensure_text(i)), None) for i in python_paths).keys())
        abs_python_paths = [i if case_sensitive else i.lower() for i in abs_python_paths]

        extra_as_python_path = extra_all[: len(abs_python_paths)]
        assert abs_python_paths == extra_as_python_path  # python paths are there at the start

        non_python_path = extra_all[len(abs_python_paths) :]
        assert non_python_path == [i for i in base if i not in extra_as_python_path]
    else:
        assert base == extra_all


@pytest.mark.skipif(
    not (CURRENT.implementation == "CPython" and PY2),
    reason="stdlib components without py files only possible on CPython2",
)
@pytest.mark.parametrize(
    "py, pyc",
    list(
        product(
            [True, False] if Python2.from_stdlib(Python2.mappings(CURRENT), "os.py")[2] else [False],
            [True, False] if Python2.from_stdlib(Python2.mappings(CURRENT), "os.pyc")[2] else [False],
        ),
    ),
)
def test_py_pyc_missing(tmp_path, mocker, session_app_data, py, pyc):
    """Ensure that creation can succeed if os.pyc exists (even if os.py has been deleted)"""
    previous = Python2.from_stdlib

    def from_stdlib(mappings, name):
        path, to, exists = previous(mappings, name)
        if name.endswith("py"):
            exists = py
        elif name.endswith("pyc"):
            exists = pyc
        return path, to, exists

    mocker.patch.object(Python2, "from_stdlib", side_effect=from_stdlib)

    result = cli_run([ensure_text(str(tmp_path)), "--without-pip", "--activators", "", "-vv"])
    py_at = Python2.from_stdlib(Python2.mappings(CURRENT), "os.py")[1](result.creator, Path("os.py"))
    py = pyc is False or py  # if pyc is False we fallback to serve the py, which will exist (as we only mock the check)
    assert py_at.exists() is py

    pyc_at = Python2.from_stdlib(Python2.mappings(CURRENT), "osc.py")[1](result.creator, Path("os.pyc"))
    assert pyc_at.exists() is pyc


def test_zip_importer_can_import_setuptools(tmp_path):
    """We're patching the loaders so might fail on r/o loaders, such as zipimporter on CPython<3.8"""
    result = cli_run([str(tmp_path / "venv"), "--activators", "", "--no-pip", "--no-wheel", "--copies"])
    zip_path = tmp_path / "site-packages.zip"
    with zipfile.ZipFile(str(zip_path), "w", zipfile.ZIP_DEFLATED) as zip_handler:
        lib = str(result.creator.purelib)
        for root, _, files in os.walk(lib):
            base = root[len(lib) :].lstrip(os.pathsep)
            for file in files:
                if not file.startswith("_virtualenv"):
                    zip_handler.write(filename=os.path.join(root, file), arcname=os.path.join(base, file))
    for folder in result.creator.purelib.iterdir():
        if not folder.name.startswith("_virtualenv"):
            if folder.is_dir():
                shutil.rmtree(str(folder), ignore_errors=True)
            else:
                folder.unlink()
    env = os.environ.copy()
    env[str("PYTHONPATH")] = str(zip_path)
    subprocess.check_call([str(result.creator.exe), "-c", "from setuptools.dist import Distribution"], env=env)


# verify that python in created virtualenv does not preimport threading.
# https://github.com/pypa/virtualenv/issues/1895
#
# coverage is disabled, because when coverage is active, it imports threading in default mode.
@pytest.mark.xfail(
    IS_PYPY and PY3 and sys.platform.startswith("darwin"),
    reason="https://foss.heptapod.net/pypy/pypy/-/issues/3269",
)
def test_no_preimport_threading(tmp_path, no_coverage):
    session = cli_run([ensure_text(str(tmp_path))])
    out = subprocess.check_output(
        [str(session.creator.exe), "-c", r"import sys; print('\n'.join(sorted(sys.modules)))"],
        universal_newlines=True,
    )
    imported = set(out.splitlines())
    assert "threading" not in imported


# verify that .pth files in site-packages/ are always processed even if $PYTHONPATH points to it.
def test_pth_in_site_vs_PYTHONPATH(tmp_path):
    session = cli_run([ensure_text(str(tmp_path))])
    site_packages = str(session.creator.purelib)
    # install test.pth that sets sys.testpth='ok'
    with open(os.path.join(site_packages, "test.pth"), "w") as f:
        f.write('import sys; sys.testpth="ok"\n')
    # verify that test.pth is activated when interpreter is run
    out = subprocess.check_output(
        [str(session.creator.exe), "-c", r"import sys; print(sys.testpth)"],
        universal_newlines=True,
    )
    assert out == "ok\n"
    # same with $PYTHONPATH pointing to site_packages
    env = os.environ.copy()
    path = [site_packages]
    if "PYTHONPATH" in env:
        path.append(env["PYTHONPATH"])
    env["PYTHONPATH"] = os.pathsep.join(path)
    out = subprocess.check_output(
        [str(session.creator.exe), "-c", r"import sys; print(sys.testpth)"],
        universal_newlines=True,
        env=env,
    )
    assert out == "ok\n"


def test_getsitepackages_system_site(tmp_path):
    # Test without --system-site-packages
    session = cli_run([ensure_text(str(tmp_path))])

    system_site_packages = get_expected_system_site_packages(session)

    out = subprocess.check_output(
        [str(session.creator.exe), "-c", r"import site; print(site.getsitepackages())"],
        universal_newlines=True,
    )
    site_packages = ast.literal_eval(out)

    for system_site_package in system_site_packages:
        assert system_site_package not in site_packages

    # Test with --system-site-packages
    session = cli_run([ensure_text(str(tmp_path)), "--system-site-packages"])

    system_site_packages = get_expected_system_site_packages(session)

    out = subprocess.check_output(
        [str(session.creator.exe), "-c", r"import site; print(site.getsitepackages())"],
        universal_newlines=True,
    )
    site_packages = ast.literal_eval(out)

    for system_site_package in system_site_packages:
        assert system_site_package in site_packages


def get_expected_system_site_packages(session):
    base_prefix = session.creator.pyenv_cfg["base-prefix"]
    base_exec_prefix = session.creator.pyenv_cfg["base-exec-prefix"]
    old_prefixes = site.PREFIXES
    site.PREFIXES = [base_prefix, base_exec_prefix]
    system_site_packages = site.getsitepackages()
    site.PREFIXES = old_prefixes

    return system_site_packages


def test_get_site_packages(tmp_path):
    case_sensitive = fs_is_case_sensitive()
    session = cli_run([ensure_text(str(tmp_path))])
    env_site_packages = [str(session.creator.purelib), str(session.creator.platlib)]
    out = subprocess.check_output(
        [str(session.creator.exe), "-c", r"import site; print(site.getsitepackages())"],
        universal_newlines=True,
    )
    site_packages = ast.literal_eval(out)

    if not case_sensitive:
        env_site_packages = [x.lower() for x in env_site_packages]
        site_packages = [x.lower() for x in site_packages]

    for env_site_package in env_site_packages:
        assert env_site_package in site_packages
