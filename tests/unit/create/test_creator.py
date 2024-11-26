from __future__ import annotations

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
from pathlib import Path
from stat import S_IREAD, S_IRGRP, S_IROTH
from textwrap import dedent
from threading import Thread

import pytest

from virtualenv.__main__ import run, run_with_catch
from virtualenv.create.creator import DEBUG_SCRIPT, Creator, get_env_debug_info
from virtualenv.create.pyenv_cfg import PyEnvCfg
from virtualenv.create.via_global_ref.builtin.cpython.common import is_macos_brew
from virtualenv.create.via_global_ref.builtin.cpython.cpython3 import CPython3Posix
from virtualenv.discovery.py_info import PythonInfo
from virtualenv.info import IS_PYPY, IS_WIN, fs_is_case_sensitive
from virtualenv.run import cli_run, session_via_cli

CURRENT = PythonInfo.current_system()


def test_os_path_sep_not_allowed(tmp_path, capsys):
    target = str(tmp_path / f"a{os.pathsep}b")
    err = _non_success_exit_code(capsys, target)
    msg = (
        f"destination {target!r} must not contain the path separator ({os.pathsep})"
        f" as this would break the activation scripts"
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
    target.write_text("", encoding="utf-8")
    err = _non_success_exit_code(capsys, str(target))
    msg = f"the destination {target!s} already exists and is a file"
    assert msg in err, err


@pytest.mark.skipif(sys.platform == "win32", reason="Windows only applies R/O to files")
def test_destination_not_write_able(tmp_path, capsys):
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        pytest.skip("no way to check permission restriction when running under root")

    target = tmp_path
    prev_mod = target.stat().st_mode
    target.chmod(S_IREAD | S_IRGRP | S_IROTH)
    try:
        err = _non_success_exit_code(capsys, str(target))
        msg = f"the destination . is not write-able at {target!s}"
        assert msg in err, err
    finally:
        target.chmod(prev_mod)


def cleanup_sys_path(paths):
    from virtualenv.create.creator import HERE  # noqa: PLC0415

    paths = [p.resolve() for p in (Path(os.path.abspath(i)) for i in paths) if p.exists()]
    to_remove = [Path(HERE)]
    if os.environ.get("PYCHARM_HELPERS_DIR"):
        to_remove.extend((Path(os.environ["PYCHARM_HELPERS_DIR"]).parent, Path(os.path.expanduser("~")) / ".PyCharm"))
    return [i for i in paths if not any(str(i).startswith(str(t)) for t in to_remove)]


@pytest.fixture(scope="session")
def system(session_app_data):
    return get_env_debug_info(Path(CURRENT.system_executable), DEBUG_SCRIPT, session_app_data, os.environ)


CURRENT_CREATORS = [i for i in CURRENT.creators().key_to_class if i != "builtin"]
CREATE_METHODS = []
for k, v in CURRENT.creators().key_to_meta.items():
    if k in CURRENT_CREATORS:
        if v.can_copy:
            if k == "venv" and CURRENT.implementation == "PyPy" and CURRENT.pypy_version_info >= [7, 3, 13]:
                continue  # https://foss.heptapod.net/pypy/pypy/-/issues/4019
            CREATE_METHODS.append((k, "copies"))
        if v.can_symlink:
            CREATE_METHODS.append((k, "symlinks"))


@pytest.mark.parametrize(
    ("creator", "isolated"),
    [pytest.param(*i, id=f"{'-'.join(i[0])}-{i[1]}") for i in product(CREATE_METHODS, ["isolated", "global"])],
)
def test_create_no_seed(  # noqa: C901, PLR0912, PLR0913, PLR0915
    python,
    creator,
    isolated,
    system,
    coverage_env,
    special_name_dir,
):
    dest = special_name_dir
    creator_key, method = creator
    cmd = [
        "-v",
        "-v",
        "-p",
        str(python),
        str(dest),
        "--without-pip",
        "--activators",
        "",
        "--creator",
        creator_key,
        f"--{method}",
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
    patch_files = {purelib / f"{'_virtualenv'}.{i}" for i in ("py", "pyc", "pth")}
    patch_files.add(purelib / "__pycache__")
    content = set(creator.purelib.iterdir()) - patch_files
    assert not content, "\n".join(str(i) for i in content)
    assert creator.env_name == str(dest.name)
    debug = creator.debug
    assert "exception" not in debug, f"{debug.get('exception')}\n{debug.get('out')}\n{debug.get('err')}"
    sys_path = cleanup_sys_path(debug["sys"]["path"])
    system_sys_path = cleanup_sys_path(system["sys"]["path"])
    our_paths = set(sys_path) - set(system_sys_path)
    our_paths_repr = "\n".join(repr(i) for i in our_paths)

    # ensure we have at least one extra path added
    assert len(our_paths) >= 1, our_paths_repr
    # ensure all additional paths are related to the virtual environment
    for path in our_paths:
        msg = "\n".join(str(p) for p in system_sys_path)
        msg = f"\n{path!s}\ndoes not start with {dest!s}\nhas:\n{msg}"
        assert str(path).startswith(str(dest)), msg
    # ensure there's at least a site-packages folder as part of the virtual environment added
    assert any(p for p in our_paths if p.parts[-1] == "site-packages"), our_paths_repr

    # ensure the global site package is added or not, depending on flag
    global_sys_path = system_sys_path[-1]
    if isolated == "isolated":
        msg = "\n".join(str(j) for j in sys_path)
        msg = f"global sys path {global_sys_path!s} is in virtual environment sys path:\n{msg}"
        assert global_sys_path not in sys_path, msg
    else:
        common = []
        for left, right in zip(reversed(system_sys_path), reversed(sys_path)):
            if left == right:
                common.append(left)
            else:
                break

        def list_to_str(iterable):
            return [str(i) for i in iterable]

        assert common, "\n".join(difflib.unified_diff(list_to_str(sys_path), list_to_str(system_sys_path)))

    # test that the python executables in the bin directory are either:
    # - files
    # - absolute symlinks outside of the venv
    # - relative symlinks inside of the venv
    if sys.platform == "win32":
        exes = ("python.exe",)
    else:
        exes = ("python", f"python{sys.version_info.major}", f"python{sys.version_info.major}.{sys.version_info.minor}")
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
            text=True,
        ).strip()
        assert result == "None"

    git_ignore = (dest / ".gitignore").read_text(encoding="utf-8")
    if creator_key == "venv" and sys.version_info >= (3, 13):
        comment = "# Created by venv; see https://docs.python.org/3/library/venv.html"
    else:
        comment = "# created by virtualenv automatically"
    assert git_ignore.splitlines() == [comment, "*"]


def test_create_vcs_ignore_exists(tmp_path):
    git_ignore = tmp_path / ".gitignore"
    git_ignore.write_text("magic", encoding="utf-8")
    cli_run([str(tmp_path), "--without-pip", "--activators", ""])
    assert git_ignore.read_text(encoding="utf-8") == "magic"


def test_create_vcs_ignore_override(tmp_path):
    git_ignore = tmp_path / ".gitignore"
    cli_run([str(tmp_path), "--without-pip", "--no-vcs-ignore", "--activators", ""])
    assert not git_ignore.exists()


def test_create_vcs_ignore_exists_override(tmp_path):
    git_ignore = tmp_path / ".gitignore"
    git_ignore.write_text("magic", encoding="utf-8")
    cli_run([str(tmp_path), "--without-pip", "--no-vcs-ignore", "--activators", ""])
    assert git_ignore.read_text(encoding="utf-8") == "magic"


@pytest.mark.skipif(not CURRENT.has_venv, reason="requires interpreter with venv")
def test_venv_fails_not_inline(tmp_path, capsys, mocker):
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        pytest.skip("no way to check permission restriction when running under root")

    def _session_via_cli(args, options=None, setup_logging=True, env=None):
        session = session_via_cli(args, options, setup_logging, env)
        assert session.creator.can_be_inline is False
        return session

    mocker.patch("virtualenv.run.session_via_cli", side_effect=_session_via_cli)
    before = tmp_path.stat().st_mode
    cfg_path = tmp_path / "pyvenv.cfg"
    cfg_path.write_text("", encoding="utf-8")
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


@pytest.mark.parametrize("creator", CURRENT_CREATORS)
@pytest.mark.parametrize("clear", [True, False], ids=["clear", "no_clear"])
def test_create_clear_resets(tmp_path, creator, clear, caplog):
    caplog.set_level(logging.DEBUG)
    if creator == "venv" and clear is False:
        pytest.skip("venv without clear might fail")
    marker = tmp_path / "magic"
    cmd = [str(tmp_path), "--seeder", "app-data", "--without-pip", "--creator", creator, "-vvv"]
    cli_run(cmd)

    marker.write_text("", encoding="utf-8")  # if we a marker file this should be gone on a clear run, remain otherwise
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
    elif creator != "venv":
        assert "prompt" in cfg, list(cfg.content.keys())
        assert cfg["prompt"] == actual_prompt


@pytest.mark.parametrize("creator", CURRENT_CREATORS)
def test_home_path_is_exe_parent(tmp_path, creator):
    cmd = [str(tmp_path), "--seeder", "app-data", "--without-pip", "--creator", creator]

    result = cli_run(cmd)
    cfg = PyEnvCfg.from_file(result.creator.pyenv_cfg.path)

    # Cannot assume "home" path is a specific value as path resolution may change
    # between versions (symlinks, framework paths, etc) but we can check that a
    # python executable is present from the configured path per PEP 405
    if sys.platform == "win32":
        exes = ("python.exe",)
    else:
        exes = (
            "python",
            f"python{sys.version_info.major}",
            f"python{sys.version_info.major}.{sys.version_info.minor}",
        )

    assert any(os.path.exists(os.path.join(cfg["home"], exe)) for exe in exes)


@pytest.mark.usefixtures("temp_app_data")
def test_create_parallel(tmp_path):
    def create(count):
        subprocess.check_call(
            [sys.executable, "-m", "virtualenv", "-vvv", str(tmp_path / f"venv{count}"), "--without-pip"],
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


@pytest.mark.usefixtures("current_fastest")
def test_create_long_path(tmp_path):
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
@pytest.mark.usefixtures("session_app_data")
def test_create_distutils_cfg(creator, tmp_path, monkeypatch):
    result = cli_run(
        [
            str(tmp_path / "venv"),
            "--activators",
            "",
            "--creator",
            creator,
            "--setuptools",
            "bundle",
            "--wheel",
            "bundle",
        ],
    )

    app = Path(__file__).parent / "console_app"
    dest = tmp_path / "console_app"
    shutil.copytree(str(app), str(dest))

    setup_cfg = dest / "setup.cfg"
    conf = dedent(
        f"""
            [install]
            prefix={tmp_path}{os.sep}prefix
            install_purelib={tmp_path}{os.sep}purelib
            install_platlib={tmp_path}{os.sep}platlib
            install_headers={tmp_path}{os.sep}headers
            install_scripts={tmp_path}{os.sep}scripts
            install_data={tmp_path}{os.sep}data
            """,
    )
    setup_cfg.write_text(setup_cfg.read_text(encoding="utf-8") + conf, encoding="utf-8")

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
        result += f"{indent}{os.path.basename(root)}/\n"
        sub = " " * 4 * (level + 1)
        for f in files:
            result += f"{sub}{f}\n"
    return result


@pytest.mark.skipif(is_macos_brew(CURRENT), reason="no copy on brew")
@pytest.mark.skip(reason="https://github.com/pypa/setuptools/issues/4640")
def test_zip_importer_can_import_setuptools(tmp_path):
    """We're patching the loaders so might fail on r/o loaders, such as zipimporter on CPython<3.8"""
    result = cli_run(
        [str(tmp_path / "venv"), "--activators", "", "--no-pip", "--no-wheel", "--copies", "--setuptools", "bundle"],
    )
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
    env["PYTHONPATH"] = str(zip_path)
    subprocess.check_call([str(result.creator.exe), "-c", "from setuptools.dist import Distribution"], env=env)


# verify that python in created virtualenv does not preimport threading.
# https://github.com/pypa/virtualenv/issues/1895
#
# coverage is disabled, because when coverage is active, it imports threading in default mode.
@pytest.mark.xfail(
    IS_PYPY and sys.platform.startswith("darwin"),
    reason="https://foss.heptapod.net/pypy/pypy/-/issues/3269",
)
@pytest.mark.usefixtures("_no_coverage")
def test_no_preimport_threading(tmp_path):
    session = cli_run([str(tmp_path)])
    out = subprocess.check_output(
        [str(session.creator.exe), "-c", r"import sys; print('\n'.join(sorted(sys.modules)))"],
        text=True,
        encoding="utf-8",
    )
    imported = set(out.splitlines())
    assert "threading" not in imported


# verify that .pth files in site-packages/ are always processed even if $PYTHONPATH points to it.
def test_pth_in_site_vs_python_path(tmp_path):
    session = cli_run([str(tmp_path)])
    site_packages = session.creator.purelib
    # install test.pth that sets sys.testpth='ok'
    (session.creator.purelib / "test.pth").write_text('import sys; sys.testpth="ok"\n', encoding="utf-8")
    # verify that test.pth is activated when interpreter is run
    out = subprocess.check_output(
        [str(session.creator.exe), "-c", r"import sys; print(sys.testpth)"],
        text=True,
        encoding="utf-8",
    )
    assert out == "ok\n"
    # same with $PYTHONPATH pointing to site_packages
    env = os.environ.copy()
    path = [str(site_packages)]
    if "PYTHONPATH" in env:
        path.append(env["PYTHONPATH"])
    env["PYTHONPATH"] = os.pathsep.join(path)
    out = subprocess.check_output(
        [str(session.creator.exe), "-c", r"import sys; print(sys.testpth)"],
        text=True,
        env=env,
        encoding="utf-8",
    )
    assert out == "ok\n"


def test_getsitepackages_system_site(tmp_path):
    # Test without --system-site-packages
    session = cli_run([str(tmp_path)])

    system_site_packages = get_expected_system_site_packages(session)

    out = subprocess.check_output(
        [str(session.creator.exe), "-c", r"import site; print(site.getsitepackages())"],
        text=True,
        encoding="utf-8",
    )
    site_packages = ast.literal_eval(out)

    for system_site_package in system_site_packages:
        assert system_site_package not in site_packages

    # Test with --system-site-packages
    session = cli_run([str(tmp_path), "--system-site-packages"])

    system_site_packages = [str(Path(i).resolve()) for i in get_expected_system_site_packages(session)]

    out = subprocess.check_output(
        [str(session.creator.exe), "-c", r"import site; print(site.getsitepackages())"],
        text=True,
        encoding="utf-8",
    )
    site_packages = [str(Path(i).resolve()) for i in ast.literal_eval(out)]

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
    session = cli_run([str(tmp_path)])
    env_site_packages = [str(session.creator.purelib), str(session.creator.platlib)]
    out = subprocess.check_output(
        [str(session.creator.exe), "-c", r"import site; print(site.getsitepackages())"],
        text=True,
        encoding="utf-8",
    )
    site_packages = ast.literal_eval(out)

    if not case_sensitive:
        env_site_packages = [x.lower() for x in env_site_packages]
        site_packages = [x.lower() for x in site_packages]

    for env_site_package in env_site_packages:
        assert env_site_package in site_packages


def test_debug_bad_virtualenv(tmp_path):
    cmd = [str(tmp_path), "--without-pip"]
    result = cli_run(cmd)
    # if the site.py is removed/altered the debug should fail as no one is around to fix the paths
    cust = result.creator.purelib / "_a.pth"
    cust.write_text(
        'import sys; sys.stdout.write("std-out"); sys.stderr.write("std-err"); raise SystemExit(1)',
        encoding="utf-8",
    )
    debug_info = result.creator.debug
    assert debug_info["returncode"] == 1
    assert "std-err" in debug_info["err"]
    assert "std-out" in debug_info["out"]
    assert debug_info["exception"]


@pytest.mark.parametrize("python_path_on", [True, False], ids=["on", "off"])
def test_python_path(monkeypatch, tmp_path, python_path_on):
    result = cli_run([str(tmp_path), "--without-pip", "--activators", ""])
    monkeypatch.chdir(tmp_path)
    case_sensitive = fs_is_case_sensitive()

    def _get_sys_path(flag=None):
        cmd = [str(result.creator.exe)]
        if flag:
            cmd.append(flag)
        cmd.extend(["-c", "import json; import sys; print(json.dumps(sys.path))"])
        return [i if case_sensitive else i.lower() for i in json.loads(subprocess.check_output(cmd, encoding="utf-8"))]

    monkeypatch.delenv("PYTHONPATH", raising=False)
    base = _get_sys_path()

    # note the value result.creator.interpreter.system_stdlib cannot be set, as that would disable our custom site.py
    python_paths = [
        str(Path(result.creator.interpreter.prefix)),
        str(Path(result.creator.interpreter.system_stdlib) / "b"),
        str(result.creator.purelib / "a"),
        str(result.creator.purelib),
        str(result.creator.bin_dir),
        str(tmp_path / "base"),
        f"{tmp_path / 'base_sep'!s}{os.sep}",
        "name",
        f"name{os.sep}",
        f"{tmp_path.parent}{f'{tmp_path.name}_suffix'}",
        ".",
        "..",
        "",
    ]
    python_path_env = os.pathsep.join(python_paths)
    monkeypatch.setenv("PYTHONPATH", python_path_env)

    extra_all = _get_sys_path(None if python_path_on else "-E")
    if python_path_on:
        assert not extra_all[0]  # the cwd is always injected at start as ''
        extra_all = extra_all[1:]
        assert not base[0]
        base = base[1:]

        assert not (set(base) - set(extra_all))  # all base paths are present
        abs_python_paths = list(OrderedDict((os.path.abspath(str(i)), None) for i in python_paths).keys())
        abs_python_paths = [i if case_sensitive else i.lower() for i in abs_python_paths]

        extra_as_python_path = extra_all[: len(abs_python_paths)]
        assert abs_python_paths == extra_as_python_path  # python paths are there at the start

        non_python_path = extra_all[len(abs_python_paths) :]
        assert non_python_path == [i for i in base if i not in extra_as_python_path]
    else:
        assert base == extra_all


# Make sure that the venv creator works on systems where vendor-delivered files
# (specifically venv scripts delivered with Python itself) are not writable.
#
# https://github.com/pypa/virtualenv/issues/2419
@pytest.mark.skipif("venv" not in CURRENT_CREATORS, reason="test needs venv creator")
def test_venv_creator_without_write_perms(tmp_path, mocker):
    from virtualenv.run.session import Session  # noqa: PLC0415

    prev = Session._create  # noqa: SLF001

    def func(self):
        prev(self)
        scripts_dir = self.creator.dest / "bin"
        for script in scripts_dir.glob("*ctivate*"):
            script.chmod(stat.S_IREAD | stat.S_IRGRP | stat.S_IROTH)

    mocker.patch("virtualenv.run.session.Session._create", side_effect=func, autospec=True)

    cmd = [str(tmp_path), "--seeder", "app-data", "--without-pip", "--creator", "venv"]
    cli_run(cmd)
