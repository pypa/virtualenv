from __future__ import annotations

import contextlib
import csv
import errno
import hashlib
import logging
import os
import sys
import zipfile
from base64 import urlsafe_b64encode
from pathlib import Path
from stat import S_IREAD, S_IWGRP, S_IWOTH, S_IWUSR
from subprocess import Popen, check_call, run
from threading import Thread
from typing import TYPE_CHECKING, Final

import pytest
from python_discovery import PythonInfo
from python_discovery import _cached_py_info as cached_py_info

from virtualenv.info import fs_supports_symlink
from virtualenv.run import cli_run
from virtualenv.seed.embed.via_app_data.pip_install.base import _safe_extract_zip
from virtualenv.seed.embed.via_app_data.pip_install.copy import CopyPipInstall
from virtualenv.seed.wheels.embed import BUNDLE_FOLDER, BUNDLE_SUPPORT
from virtualenv.util.path import safe_delete

if TYPE_CHECKING:
    from collections.abc import Callable

    from pytest_mock import MockerFixture

    from virtualenv.run.session import Session


@pytest.mark.parametrize(
    "source",
    [
        pytest.param("environment", id="environment"),
        pytest.param("configuration", id="configuration"),
        pytest.param("command-line", id="command-line"),
    ],
)
def test_transient_seed_survives_cache_cleanup(tmp_path: Path, source: str, unusable_cache: Path) -> None:
    config: Final = tmp_path / "virtualenv.ini"
    config.write_text("[virtualenv]\nsymlink_app_data = true\n" if source == "configuration" else "", encoding="utf-8")
    env: Final = {
        **os.environ,
        "VIRTUALENV_CONFIG_FILE": str(config),
        "VIRTUALENV_OVERRIDE_APP_DATA": str(unusable_cache),
    }
    if source == "environment":
        env["VIRTUALENV_SYMLINK_APP_DATA"] = "true"
    args: Final = [str(tmp_path / "env"), "--no-periodic-update", "--no-setuptools"]
    if source == "command-line":
        args.append("--symlink-app-data")
    session: Final = cli_run(args, env=env)
    assert (
        session.creator.app_data.transient,
        Path(str(session.creator.app_data)).exists(),
        (session.creator.purelib / "pip" / "__init__.py").is_file(),
    ) == (True, False, True)


def test_transient_seed_reports_copy_fallback(
    tmp_path: Path, caplog: pytest.LogCaptureFixture, unusable_cache: Path
) -> None:
    caplog.set_level(logging.DEBUG)
    cli_run(
        [str(tmp_path / "env"), "--no-periodic-update", "--no-setuptools"],
        env={**os.environ, "VIRTUALENV_OVERRIDE_APP_DATA": str(unusable_cache), "VIRTUALENV_SYMLINK_APP_DATA": "true"},
        setup_logging=False,
    )
    assert "copy seed packages because temporary app-data is removed after creation" in caplog.text


@pytest.fixture
def unusable_cache(tmp_path: Path) -> Path:
    blocked: Final = tmp_path / "blocked"
    blocked.touch()
    return blocked / "cache"


@pytest.mark.parametrize(
    ("config_text", "env_vars", "flags"),
    [
        pytest.param("", {"VIRTUALENV_SYMLINK_APP_DATA": "true"}, (), id="environment"),
        pytest.param("[virtualenv]\nsymlink_app_data = true\n", {}, (), id="configuration"),
        pytest.param("", {}, ("--symlink-app-data",), id="command-line"),
    ],
)
@pytest.mark.usefixtures("symlinks_unsupported")
def test_seed_copies_when_symlinks_unsupported(
    tmp_path: Path, config_text: str, env_vars: dict[str, str], flags: tuple[str, ...]
) -> None:
    config: Final = tmp_path / "virtualenv.ini"
    config.write_text(config_text, encoding="utf-8")
    session: Final = cli_run(
        [
            str(tmp_path / "env"),
            "--app-data",
            str(tmp_path / "cache"),
            "--no-periodic-update",
            "--no-setuptools",
            *flags,
        ],
        env={**os.environ, "VIRTUALENV_CONFIG_FILE": str(config), **env_vars},
    )
    pip: Final = session.creator.purelib / "pip"
    assert (
        session.creator.app_data.transient,
        pip.is_symlink(),
        (pip / "__init__.py").is_file(),
    ) == (False, False, True)


@pytest.mark.usefixtures("symlinks_unsupported")
def test_seed_reports_copy_fallback_when_symlinks_unsupported(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG)
    cli_run(
        [str(tmp_path / "env"), "--app-data", str(tmp_path / "cache"), "--no-periodic-update", "--no-setuptools"],
        env={**os.environ, "VIRTUALENV_SYMLINK_APP_DATA": "true"},
        setup_logging=False,
    )
    assert "copy seed packages because the filesystem does not support symlinks" in caplog.text


@pytest.fixture
def symlinks_unsupported(mocker: MockerFixture) -> None:
    mocker.patch(
        "virtualenv.seed.embed.via_app_data.via_app_data.fs_supports_symlink", autospec=True, return_value=False
    )


@pytest.mark.skipif(not fs_supports_symlink(), reason="requires symlinks")
@pytest.mark.parametrize(
    ("where", "name"),
    [pytest.param("cwd", "compileall.py", id="cwd-module"), pytest.param("purelib", "planted.pth", id="site-pth")],
)
def test_seed_image_compiles_in_isolation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, where: str, name: str
) -> None:
    cmd: Final = [
        str(tmp_path / "env"),
        "--app-data",
        str(tmp_path / "cache"),
        "--symlink-app-data",
        "--no-periodic-update",
        "--no-setuptools",
    ]
    purelib: Final = cli_run([*cmd, "--without-pip"]).creator.purelib
    marker: Final = tmp_path / "marker"
    planted: Final = {"cwd": tmp_path, "purelib": purelib}[where] / name
    planted.write_text(f"import pathlib; pathlib.Path({str(marker)!r}).touch()", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    session: Final = cli_run(cmd)
    assert list((session.creator.purelib / "pip" / "__pycache__").glob("__init__.*.pyc"))
    assert not marker.exists()


@pytest.mark.usefixtures("_no_coverage")
@pytest.mark.parametrize(
    ("metadata_file", "content"),
    [
        pytest.param("top_level.txt", "pip\n{dest}\n", id="top-level-env-root"),
        pytest.param("top_level.txt", "pip\n\n", id="top-level-blank"),
        pytest.param("RECORD", "{record}\n{outside},,", id="record-traversal"),
    ],
)
def test_seed_metadata_cleanup_stays_inside_package(
    tmp_path: Path, caplog: pytest.LogCaptureFixture, metadata_file: str, content: str
) -> None:
    args: Final = [str(tmp_path / "env"), "--pip", "embed", "--no-periodic-update"]
    session: Final = cli_run(args, setup_logging=False)
    purelib: Final = session.creator.purelib
    markers: Final = [tmp_path / "keep.txt", session.creator.dest / "keep.txt", purelib / "keep.txt"]
    for marker in markers:
        marker.write_text("keep", encoding="utf-8")
    dist_info: Final = next(purelib.glob("pip-*.dist-info"))
    (dist_info / metadata_file).write_text(
        content.format(
            dest=session.creator.dest,
            outside=os.path.relpath(markers[0], purelib),
            record=(dist_info / "RECORD").read_text(encoding="utf-8"),
        ),
        encoding="utf-8",
    )
    cli_run(args, setup_logging=False)
    assert (
        [i.exists() for i in markers],
        (purelib / "pip" / "__init__.py").is_file(),
        "skip removal of" in caplog.text,
    ) == (
        [True, True, True],
        True,
        True,
    )


@pytest.mark.skipif(not fs_supports_symlink(), reason="symlinks are unavailable")
def test_seed_metadata_unlinks_symlink_without_following(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    args: Final = [str(tmp_path / "env"), "--pip", "embed", "--no-periodic-update"]
    session: Final = cli_run(args, setup_logging=False)
    outside: Final = tmp_path / "outside"
    outside.mkdir()
    (outside / "keep.txt").write_text("keep", encoding="utf-8")
    link: Final = session.creator.purelib / "linked"
    link.symlink_to(outside, target_is_directory=True)
    record: Final = next(session.creator.purelib.glob("pip-*.dist-info")) / "RECORD"
    record.write_text(f"{record.read_text(encoding='utf-8')}\nlinked,,", encoding="utf-8")
    cli_run(args, setup_logging=False)
    assert (link.is_symlink(), (outside / "keep.txt").exists(), "skip removal of" in caplog.text) == (
        False,
        True,
        False,
    )


@pytest.mark.parametrize(
    "linked",
    [
        pytest.param(False, id="copy"),
        pytest.param(
            True, id="symlink", marks=pytest.mark.skipif(not fs_supports_symlink(), reason="symlinks are unavailable")
        ),
    ],
)
def test_seed_metadata_keeps_reseeding_supported(
    tmp_path: Path, linked: bool, caplog: pytest.LogCaptureFixture
) -> None:
    args: Final = [
        str(tmp_path / "env"),
        "--pip",
        "embed",
        "--no-periodic-update",
        *(["--symlink-app-data"] if linked else []),
    ]
    cli_run(args, setup_logging=False)
    session: Final = cli_run(args, setup_logging=False)
    package: Final = session.creator.purelib / "pip"
    assert ((package / "__init__.py").is_file(), package.is_symlink(), "skip removal of" in caplog.text) == (
        True,
        linked,
        False,
    )


@pytest.mark.usefixtures("_no_coverage")
@pytest.mark.skipif(os.name != "nt", reason="Windows refuses to delete read-only files")
def test_reseed_over_read_only_environment(tmp_path: Path) -> None:
    args: Final = [str(tmp_path / "env"), "--copies", "--pip", "embed", "--no-periodic-update"]
    dest: Final = cli_run(args, setup_logging=False).creator.dest
    # chmod follows a link on newer Pythons and would mark the base interpreter read-only
    for path in (entry for entry in dest.rglob("*") if entry.is_file() and not entry.is_symlink()):
        path.chmod(S_IREAD)
    session: Final = cli_run(args, setup_logging=False)
    assert (session.creator.purelib / "pip" / "__init__.py").is_file()


@pytest.mark.parametrize(
    "name",
    [
        pytest.param("plain", id="plain"),
        pytest.param("two words", id="space"),
        pytest.param("owner's env", id="apostrophe"),
        pytest.param("$(echo a) `echo b`", id="command-substitution"),
        pytest.param("a" * 120, id="long", marks=pytest.mark.skipif(os.name == "nt", reason="POSIX shebang limit")),
        pytest.param("env \\path", id="backslash", marks=pytest.mark.skipif(os.name == "nt", reason="POSIX filename")),
        pytest.param("env\tname", id="tab", marks=pytest.mark.skipif(os.name == "nt", reason="POSIX filename")),
    ],
)
@pytest.mark.parametrize(
    "via_python",
    [
        pytest.param(False, id="launcher"),
        pytest.param(
            True, id="python", marks=pytest.mark.skipif(os.name == "nt", reason="Windows launcher is an executable")
        ),
    ],
)
@pytest.mark.parametrize("seeder", [pytest.param("app-data", id="app-data"), pytest.param("pip", id="pip")])
def test_console_script_preserves_interpreter_path(
    tmp_path: Path, current_fastest: str, name: str, via_python: bool, seeder: str
) -> None:
    destination: Final = os.path.join(str(tmp_path), name, "env")
    run(
        [
            sys.executable,
            "-m",
            "virtualenv",
            destination,
            "--seeder",
            seeder,
            "--creator",
            current_fastest,
            "--activators",
            "",
            "--no-periodic-update",
            "--pip",
            "embed",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
        check=True,
    )
    scripts: Final = os.path.join(destination, "Scripts" if os.name == "nt" else "bin")
    result: Final = run(
        [
            *([os.path.join(scripts, "python")] if via_python else []),
            os.path.join(scripts, "pip.exe" if os.name == "nt" else "pip"),
            "--version",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
        check=True,
    )
    assert os.path.normcase(destination) in os.path.normcase(result.stdout)


@pytest.mark.slow
@pytest.mark.parametrize("copies", [False, True] if fs_supports_symlink() else [True])
def test_seed_link_via_app_data(tmp_path, coverage_env, current_fastest, copies) -> None:
    current = PythonInfo.current_system()
    bundle_ver = BUNDLE_SUPPORT[current.version_release_str]
    create_cmd = [
        str(tmp_path / "en v"),  # space in the name to ensure generated scripts work when path has space
        "--no-periodic-update",
        "--seeder",
        "app-data",
        "--extra-search-dir",
        str(BUNDLE_FOLDER),
        "--download",
        "--pip",
        bundle_ver["pip"].split("-")[1],
        "--setuptools",
        bundle_ver["setuptools"].split("-")[1],
        "--reset-app-data",
        "--creator",
        current_fastest,
        "-vv",
    ]
    if not copies:
        create_cmd.append("--symlink-app-data")
    result = cli_run(create_cmd)
    coverage_env()
    assert result

    # uninstalling pip/setuptools now should leave us with a ensure_safe_to_do env
    site_package = result.creator.purelib
    pip = site_package / "pip"
    setuptools = site_package / "setuptools"

    files_post_first_create = set(site_package.iterdir())
    assert pip in files_post_first_create
    assert setuptools in files_post_first_create
    for pip_exe in [
        result.creator.script_dir / f"pip{suffix}{result.creator.exe.suffix}"
        for suffix in (
            "",
            f"{current.version_info.major}",
            f"{current.version_info.major}.{current.version_info.minor}",
            f"-{current.version_info.major}.{current.version_info.minor}",
        )
    ]:
        assert pip_exe.exists()
        process = Popen([str(pip_exe), "--version", "--disable-pip-version-check"])
        _, __ = process.communicate()
        assert not process.returncode

    remove_cmd = [
        str(result.creator.script("pip")),
        "--verbose",
        "--disable-pip-version-check",
        "uninstall",
        "-y",
        "setuptools",
    ]
    process = Popen(remove_cmd)
    _, __ = process.communicate()
    assert not process.returncode
    assert site_package.exists()

    files_post_first_uninstall = set(site_package.iterdir())
    assert pip in files_post_first_uninstall
    assert setuptools not in files_post_first_uninstall

    # install a different setuptools to test that virtualenv removes this before installing new
    version = f"setuptools<{bundle_ver['setuptools'].split('-')[1]}"
    install_cmd = [str(result.creator.script("pip")), "--verbose", "--disable-pip-version-check", "install", version]
    process = Popen(install_cmd)
    process.communicate()
    assert not process.returncode
    assert site_package.exists()
    files_post_downgrade = set(site_package.iterdir())
    assert setuptools in files_post_downgrade

    # check we can run it again and will work - checks both overwrite and reuse cache
    result = cli_run(create_cmd)
    coverage_env()
    assert result
    files_post_second_create = set(site_package.iterdir())
    assert files_post_first_create == files_post_second_create

    # Windows does not allow removing a executable while running it, so when uninstalling pip we need to do it via
    # python -m pip
    remove_cmd = [str(result.creator.exe), "-m", "pip", *remove_cmd[1:]]
    process = Popen([*remove_cmd, "pip", "wheel"])
    _, __ = process.communicate()
    assert not process.returncode
    # pip is greedy here, removing all packages removes the site-package too
    if site_package.exists():
        purelib = result.creator.purelib
        patch_files = {purelib / f"{'_virtualenv'}.{i}" for i in ("py", "pyc", "pth")}
        patch_files.add(purelib / "__pycache__")
        post_run = set(site_package.iterdir()) - patch_files
        assert not post_run, "\n".join(str(i) for i in post_run)


@contextlib.contextmanager
def read_only_dir(d):
    write = S_IWUSR | S_IWGRP | S_IWOTH
    for root, _, filenames in os.walk(str(d)):
        os.chmod(root, os.stat(root).st_mode & ~write)
        for filename in filenames:
            name = os.path.join(root, filename)
            os.chmod(name, os.stat(name).st_mode & ~write)
    try:
        yield
    finally:
        for root, _, filenames in os.walk(str(d)):
            os.chmod(root, os.stat(root).st_mode | write)
            for filename in filenames:
                name = os.path.join(root, filename)
                os.chmod(name, os.stat(name).st_mode | write)


@pytest.fixture
def read_only_app_data(temp_app_data):
    temp_app_data.mkdir()
    with read_only_dir(temp_app_data):
        yield temp_app_data


@pytest.mark.slow
@pytest.mark.skipif(sys.platform == "win32", reason="Windows only applies R/O to files")
@pytest.mark.usefixtures("read_only_app_data")
def test_base_bootstrap_link_via_app_data_not_writable(tmp_path, current_fastest) -> None:
    dest = tmp_path / "venv"
    result = cli_run(["--seeder", "app-data", "--creator", current_fastest, "-vv", str(dest)])
    assert result


@pytest.mark.slow
@pytest.mark.skipif(sys.platform == "win32", reason="Windows only applies R/O to files")
def test_populated_read_only_cache_and_symlinked_app_data(tmp_path, current_fastest, temp_app_data) -> None:
    dest = tmp_path / "venv"
    cmd = [
        "--seeder",
        "app-data",
        "--creator",
        current_fastest,
        "--symlink-app-data",
        "-vv",
        str(dest),
    ]

    assert cli_run(cmd)
    check_call((str(dest.joinpath("bin/python")), "-c", "import pip"))

    cached_py_info._CACHE.clear()  # ruff:ignore[private-member-access]  # necessary to re-trigger py info discovery
    safe_delete(dest)

    # should succeed with special flag when read-only
    with read_only_dir(temp_app_data):
        assert cli_run(["--read-only-app-data", *cmd])
        check_call((str(dest.joinpath("bin/python")), "-c", "import pip"))


@pytest.mark.slow
@pytest.mark.skipif(sys.platform == "win32", reason="Windows only applies R/O to files")
def test_populated_read_only_cache_and_copied_app_data(tmp_path, current_fastest, temp_app_data) -> None:
    dest = tmp_path / "venv"
    cmd = [
        "--seeder",
        "app-data",
        "--creator",
        current_fastest,
        "-vv",
        "-p",
        "python",
        str(dest),
    ]

    assert cli_run(cmd)

    cached_py_info._CACHE.clear()  # ruff:ignore[private-member-access]  # necessary to re-trigger py info discovery
    safe_delete(dest)

    # should succeed with special flag when read-only
    with read_only_dir(temp_app_data):
        assert cli_run(["--read-only-app-data", *cmd])


@pytest.mark.slow
@pytest.mark.parametrize("pkg", ["pip", "setuptools"])
@pytest.mark.usefixtures("session_app_data", "current_fastest", "coverage_env")
def test_base_bootstrap_link_via_app_data_no(tmp_path, pkg) -> None:
    create_cmd = [str(tmp_path), "--seeder", "app-data", f"--no-{pkg}", "--setuptools", "bundle"]
    result = cli_run(create_cmd)
    assert not (result.creator.purelib / pkg).exists()
    for key in {"pip", "setuptools"} - {pkg}:
        assert (result.creator.purelib / key).exists()


@pytest.mark.usefixtures("temp_app_data")
def test_app_data_parallel_ok(tmp_path) -> None:
    exceptions = _run_parallel_threads(tmp_path)
    assert not exceptions, "\n".join(exceptions)


@pytest.mark.usefixtures("temp_app_data")
def test_app_data_parallel_fail(tmp_path: Path, mocker: MockerFixture) -> None:
    mocker.patch("virtualenv.seed.embed.via_app_data.pip_install.base.PipInstall.build_image", side_effect=RuntimeError)
    exceptions = _run_parallel_threads(tmp_path)
    assert len(exceptions) == 2
    for exception in exceptions:
        assert exception.startswith("failed to build image pip because:\nTraceback")
        assert "RuntimeError" in exception, exception


def _run_parallel_threads(tmp_path):
    exceptions = []

    def _run(name) -> None:
        try:
            cmd = ["--seeder", "app-data", str(tmp_path / name), "--no-setuptools"]
            cli_run(cmd)
        except Exception as exception:  # ruff:ignore[blind-except]
            as_str = str(exception)
            exceptions.append(as_str)

    threads = [Thread(target=_run, args=(f"env{i}",)) for i in range(1, 3)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    return exceptions


_DISK_FULL: Final = OSError(errno.ENOSPC, "No space left on device")


def _fail_during_extraction(zip_ref: zipfile.ZipFile, target_dir: Path) -> None:
    # stop short of the last entries, where the wheel keeps its dist-info files
    for info in zip_ref.infolist()[:-5]:
        zip_ref.extract(info, str(target_dir))
    raise _DISK_FULL


@pytest.mark.parametrize(
    ("target", "failure", "linked"),
    [
        pytest.param("base._safe_extract_zip", _fail_during_extraction, False, id="copy-extract"),
        pytest.param("base.PipInstall._generate_new_files", _DISK_FULL, False, id="copy-finish"),
        pytest.param(
            "base._safe_extract_zip",
            _fail_during_extraction,
            True,
            id="symlink-extract",
            marks=pytest.mark.skipif(not fs_supports_symlink(), reason="symlinks are unavailable"),
        ),
        pytest.param(
            "base.PipInstall._generate_new_files",
            _DISK_FULL,
            True,
            id="symlink-finish",
            marks=pytest.mark.skipif(not fs_supports_symlink(), reason="symlinks are unavailable"),
        ),
        pytest.param(
            "symlink.set_tree",
            _DISK_FULL,
            True,
            id="symlink-read-only",
            marks=pytest.mark.skipif(not fs_supports_symlink(), reason="symlinks are unavailable"),
        ),
    ],
)
def test_seed_image_build_failure_leaves_no_partial_image(
    tmp_path: Path,
    mocker: MockerFixture,
    target: str,
    failure: Callable[[zipfile.ZipFile, Path], None] | OSError,
    linked: bool,
) -> None:
    cache: Final = tmp_path / "cache"
    args: Final = [
        str(tmp_path / "env"),
        "--app-data",
        str(cache),
        "--no-periodic-update",
        "--no-setuptools",
        *(["--symlink-app-data"] if linked else []),
    ]
    patched: Final = mocker.patch(f"virtualenv.seed.embed.via_app_data.pip_install.{target}", side_effect=failure)
    with pytest.raises(RuntimeError, match="No space left on device"):
        cli_run(args, setup_logging=False)
    mocker.stop(patched)
    installer: Final = "SymlinkPipInstall" if linked else "CopyPipInstall"
    images: Final = next(cache.glob("wheel/*/image/1"))
    left: Final = sorted(i.name for i in [*images.iterdir(), *(images / installer).iterdir()] if i.is_dir())
    purelib: Final = cli_run(args, setup_logging=False).creator.purelib
    dist_info: Final = next(purelib.glob("pip-*.dist-info"))
    assert (
        left,
        (dist_info / "INSTALLER").is_file(),
        (dist_info / "RECORD").is_file(),
        (purelib / f"{dist_info.stem}.virtualenv").is_file(),
    ) == ([installer], True, True, True)


@pytest.mark.parametrize(
    ("leftover", "files", "kept"),
    [
        pytest.param("CopyPipInstall-{}", ("pip.py",), False, id="killed-build"),
        pytest.param("CopyPipInstall/{}", (), True, id="empty-image"),
    ],
)
def test_seed_image_build_replaces_leftovers(tmp_path: Path, leftover: str, files: tuple[str, ...], kept: bool) -> None:
    cache: Final = tmp_path / "cache"
    version: Final = PythonInfo.current_system().version_release_str
    path: Final = cache / "wheel" / version / "image" / "1" / leftover.format(Path(BUNDLE_SUPPORT[version]["pip"]).stem)
    path.mkdir(parents=True)
    for name in files:
        (path / name).write_text("", encoding="utf-8")
    args: Final = [str(tmp_path / "env"), "--app-data", str(cache), "--no-periodic-update", "--no-setuptools"]
    purelib: Final = cli_run([*args, "--pip", "embed"], setup_logging=False).creator.purelib
    assert (path.exists(), (next(purelib.glob("pip-*.dist-info")) / "RECORD").is_file()) == (kept, True)


def test_seed_image_build_direct_call(tmp_path: Path) -> None:
    session: Final = cli_run([str(tmp_path / "env"), "--no-seed"], setup_logging=False)
    wheel: Final = BUNDLE_FOLDER / BUNDLE_SUPPORT[session.interpreter.version_release_str]["pip"]
    image: Final = tmp_path / "image" / "CopyPipInstall" / wheel.stem
    installer: Final = CopyPipInstall(wheel, session.creator, image)
    installer.build_image()
    installer.install(session.interpreter.version_info)
    assert (
        sorted(i.name for i in image.parent.parent.iterdir()),
        (next(image.glob("*.dist-info")) / "INSTALLER").is_file(),
        session.creator.script("pip").exists(),
    ) == (["CopyPipInstall"], True, True)


def _write_zip_with_entry(zip_path: Path, entry_name: str) -> None:
    with zipfile.ZipFile(str(zip_path), "w") as archive:
        archive.writestr(entry_name, "payload")


def test_safe_extract_zip_allows_normal_entry(tmp_path: Path) -> None:
    archive = tmp_path / "ok.zip"
    _write_zip_with_entry(archive, "pkg/inner.txt")
    target = tmp_path / "out"
    target.mkdir()

    with zipfile.ZipFile(str(archive)) as zip_ref:
        _safe_extract_zip(zip_ref, target)

    assert (target / "pkg" / "inner.txt").read_text(encoding="utf-8") == "payload"


def test_safe_extract_zip_rejects_parent_traversal(tmp_path: Path) -> None:
    archive = tmp_path / "evil.zip"
    _write_zip_with_entry(archive, "../escape.txt")
    target = tmp_path / "out"
    target.mkdir()

    with zipfile.ZipFile(str(archive)) as zip_ref, pytest.raises(RuntimeError, match="escaping target directory"):
        _safe_extract_zip(zip_ref, target)

    assert not (tmp_path / "escape.txt").exists()


@pytest.mark.parametrize(
    "entry",
    [
        pytest.param("/tmp/evil.txt", id="posix"),  # ruff:ignore[hardcoded-temp-file]
        pytest.param("C:/Windows/System32/evil.txt", id="windows"),
    ],
)
def test_safe_extract_zip_rejects_absolute_entry(tmp_path: Path, entry: str) -> None:
    archive = tmp_path / "abs.zip"
    _write_zip_with_entry(archive, entry)
    target = tmp_path / "out"
    target.mkdir()

    with zipfile.ZipFile(str(archive)) as zip_ref, pytest.raises(RuntimeError, match="absolute path"):
        _safe_extract_zip(zip_ref, target)


def test_seed_entry_points_preserve_case_and_last_duplicate(tmp_path: Path) -> None:
    session = cli_run([str(tmp_path / "env"), "--no-seed"])
    image = tmp_path / "image"
    metadata = image / "example-1.dist-info"
    metadata.mkdir(parents=True)
    (metadata / "entry_points.txt").write_text(
        "[console_scripts]\nMyTool = old:main\nMyTool = example:main\n", encoding="utf-8"
    )
    CopyPipInstall(tmp_path / "example-1-py3-none-any.whl", session.creator, image).install(
        session.interpreter.version_info
    )
    script = session.creator.script("MyTool")
    if sys.platform == "win32":
        with zipfile.ZipFile(script) as archive:
            source = archive.read("__main__.py")
    else:
        source = script.read_bytes()
    assert b"from example import main" in source


@pytest.mark.parametrize(
    "script_name",
    [
        pytest.param("python3-config", id="interpreter-like"),
        pytest.param("2to3", id="leading-digits"),
        pytest.param("3to2", id="trailing-digits-after-text"),
    ],
)
def test_seed_entry_points_keep_names_that_are_not_version_suffixes(
    no_seed_session: Session, install_console_scripts: Callable[[str], None], script_name: str
) -> None:
    install_console_scripts(f"{script_name} = example:main\n")
    assert no_seed_session.creator.script(script_name).exists(), (
        f"{script_name} was not installed; got {sorted(i.name for i in no_seed_session.creator.script_dir.iterdir())}"
    )


def test_seed_entry_points_do_not_overwrite_the_interpreter(
    no_seed_session: Session, install_console_scripts: Callable[[str], None]
) -> None:
    original: Final = no_seed_session.creator.exe.read_bytes()
    install_console_scripts("python3-config = example:main\n")
    assert no_seed_session.creator.exe.read_bytes() == original, "a generated script replaced the interpreter"


def test_seed_entry_points_still_fold_version_suffixed_names(
    no_seed_session: Session, install_console_scripts: Callable[[str], None]
) -> None:
    major, minor = no_seed_session.interpreter.version_info[:2]
    install_console_scripts(f"pip{major}.{minor} = example:main\npip{major} = example:main\n")
    # a single base regenerates these, an extra one per declared name would add names like `pip33`
    expected: Final = ("pip", f"pip{major}", f"pip{major}.{minor}", f"pip-{major}.{minor}")
    assert [name for name in expected if not no_seed_session.creator.script(name).exists()] == []


@pytest.fixture
def no_seed_session(tmp_path: Path) -> Session:
    return cli_run([str(tmp_path / "env"), "--no-seed"])


@pytest.fixture
def install_console_scripts(tmp_path: Path, no_seed_session: Session) -> Callable[[str], None]:
    def install(entries: str) -> None:
        image: Final = tmp_path / "image"
        metadata: Final = image / "example-1.dist-info"
        metadata.mkdir(parents=True)
        (metadata / "entry_points.txt").write_text(f"[console_scripts]\n{entries}", encoding="utf-8")
        CopyPipInstall(tmp_path / "example-1-py3-none-any.whl", no_seed_session.creator, image).install(
            no_seed_session.interpreter.version_info
        )

    return install


@pytest.mark.skipif(not fs_supports_symlink(), reason="requires symlinks")
def test_symlink_seed_compiles_with_empty_local_module(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "compileall.py").touch()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PYTHONHOME", sys.base_prefix)
    session: Final = cli_run([
        str(tmp_path / "env"),
        "--symlink-app-data",
        "--pip",
        "embed",
        "--app-data",
        str(tmp_path / "cache"),
        "--no-periodic-update",
    ])
    assert list((session.creator.purelib / "pip" / "__pycache__").glob("__init__*.pyc"))


@pytest.mark.skipif(not fs_supports_symlink(), reason="requires symlinks")
def test_symlink_seed_reports_compilation_failure(tmp_path: Path, mocker: MockerFixture) -> None:
    mocker.patch(
        "virtualenv.seed.embed.via_app_data.pip_install.symlink.run_cmd",
        autospec=True,
        return_value=(7, "", "compilation failed"),
    )
    with pytest.raises(RuntimeError, match="compilation failed"):
        cli_run([
            str(tmp_path / "env"),
            "--symlink-app-data",
            "--pip",
            "embed",
            "--app-data",
            str(tmp_path / "cache"),
            "--no-periodic-update",
        ])


@pytest.mark.skipif(os.name != "posix", reason="POSIX shell launchers")
@pytest.mark.parametrize(
    ("name", "via_shell"),
    [
        pytest.param("plain", False, id="plain"),
        pytest.param("two words", True, id="space"),
        pytest.param("env\tname", True, id="tab"),
    ],
)
def test_pip_launcher_record_matches_contents(tmp_path: Path, name: str, via_shell: bool) -> None:
    session: Final = cli_run([str(tmp_path / name), "--seeder", "pip", "--pip", "embed", "--no-periodic-update"])
    record: Final = next(session.creator.purelib.glob("pip-*.dist-info/RECORD"))
    with record.open(encoding="utf-8", newline="") as stream:
        row: Final = next(row for row in csv.reader(stream) if row[0].endswith("/bin/pip"))
    content: Final = (session.creator.script_dir / "pip").read_bytes()
    assert content.startswith(b"#!/bin/sh\n") is via_shell
    assert row[1:] == [
        "sha256=" + urlsafe_b64encode(hashlib.sha256(content).digest()).rstrip(b"=").decode("ascii"),
        str(len(content)),
    ]
