from __future__ import annotations

import json
import os
import select
import signal
import subprocess
import sys
from pathlib import Path
from shutil import copyfile, copytree
from time import monotonic
from typing import TYPE_CHECKING, Final
from zipfile import ZipFile

import pytest
from python_discovery import PythonInfo

from virtualenv.info import fs_supports_symlink
from virtualenv.run import cli_run, session_via_cli
from virtualenv.seed.wheels.embed import BUNDLE_FOLDER, BUNDLE_SUPPORT, MAX, MIN, get_embed_wheel
from virtualenv.util.path import safe_delete

if TYPE_CHECKING:
    from collections.abc import Callable
    from types import FrameType

    from pytest_mock import MockerFixture, MockType

    from virtualenv.run.session import Session

_LAUNCHER_NAME: Final[str] = "pip.exe" if os.name == "nt" else "pip"


@pytest.mark.skipif(not fs_supports_symlink(), reason="symlinks are unavailable")
def test_pip_reseed_keeps_shared_image(linked_seed: Session) -> None:
    package: Final[Path] = linked_seed.creator.purelib / "pip"
    image: Final[Path] = package.resolve().parent
    before: Final[dict[str, tuple[bytes, int]]] = {
        str(path.relative_to(image)): (path.read_bytes(), path.stat().st_mode)
        for path in image.rglob("*")
        if path.is_file()
    }
    cli_run([str(linked_seed.creator.dest), "--seeder", "pip", "--pip", "embed", "--no-periodic-update"])
    assert {
        str(path.relative_to(image)): (path.read_bytes(), path.stat().st_mode)
        for path in image.rglob("*")
        if path.is_file()
    } == before


@pytest.mark.skipif(not fs_supports_symlink(), reason="symlinks are unavailable")
def test_pip_reseed_installs_local_package(linked_seed: Session) -> None:
    cli_run([str(linked_seed.creator.dest), "--seeder", "pip", "--pip", "embed", "--no-periodic-update"])
    result: Final[subprocess.CompletedProcess[str]] = subprocess.run(
        [str(linked_seed.creator.exe), "-I", "-m", "pip", "--version"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    assert not (linked_seed.creator.purelib / "pip").is_symlink()
    assert os.path.normcase(str(linked_seed.creator.purelib)) in os.path.normcase(result.stdout)


@pytest.mark.skipif(not fs_supports_symlink(), reason="symlinks are unavailable")
def test_pip_reseed_keeps_unrelated_launcher(linked_seed: Session) -> None:
    unrelated: Final[Path] = linked_seed.creator.script_dir / "unrelated-tool"
    unrelated.symlink_to(linked_seed.creator.dest / "missing-tool")
    cli_run([str(linked_seed.creator.dest), "--seeder", "pip", "--pip", "embed", "--no-periodic-update"])
    assert (unrelated.is_symlink(), unrelated.exists()) == (True, False)


@pytest.mark.skipif(not fs_supports_symlink(), reason="symlinks are unavailable")
@pytest.mark.parametrize(
    ("name", "directory", "remove"),
    [
        pytest.param("__main__.py", False, Path.unlink, id="file"),
        pytest.param("_internal", True, safe_delete, id="directory"),
    ],
)
def test_pip_reseed_replaces_nested_link(
    linked_seed: Session, name: str, directory: bool, remove: Callable[[Path], object]
) -> None:
    package: Final[Path] = linked_seed.creator.purelib / "pip"
    source: Final[Path] = package.resolve()
    package.unlink()
    copytree(source, package)
    for path in filter(Path.is_file, package.rglob("*")):
        path.chmod(0o600)
    entry: Final[Path] = package / name
    remove(entry)
    entry.symlink_to(source / name, target_is_directory=directory)
    cli_run([str(linked_seed.creator.dest), "--seeder", "pip", "--pip", "embed", "--no-periodic-update"])
    assert (entry.exists(), entry.is_symlink()) == (True, False)


@pytest.mark.skipif(os.name == "nt" or os.geteuid() == 0, reason="POSIX listing permissions that root bypasses")
@pytest.mark.parametrize("folder", [pytest.param("", id="package"), pytest.param("_vendor", id="nested")])
def test_pip_reseed_rejects_unlistable_folder(prepared_pip_session: Session, tmp_path: Path, folder: str) -> None:
    unlistable: Final[Path] = prepared_pip_session.creator.purelib / "pip" / folder
    unlistable.mkdir(parents=True)
    outside: Final[Path] = tmp_path / "outside"
    outside.mkdir()
    (unlistable / "_internal").symlink_to(outside, target_is_directory=True)
    unlistable.chmod(0o300)
    try:
        with pytest.raises(PermissionError):
            prepared_pip_session.seeder.run(prepared_pip_session.creator)
    finally:
        unlistable.chmod(0o700)
    assert list(outside.iterdir()) == []


def test_pip_reseed_detaches_hardlinked_metadata(prepared_pip_session: Session, tmp_path: Path) -> None:
    version: Final[str] = prepared_pip_session.creator.interpreter.version_release_str
    metadata: Final[Path] = (
        prepared_pip_session.creator.purelib / f"pip-{get_embed_wheel('pip', version).version}.dist-info"
    )
    metadata.mkdir(parents=True)
    outside: Final[Path] = tmp_path / "notes.txt"
    outside.write_text("original\n", encoding="utf-8")
    os.link(outside, metadata / "REQUESTED")

    prepared_pip_session.seeder.run(prepared_pip_session.creator)

    assert outside.read_text(encoding="utf-8") == "original\n"


@pytest.fixture
def prepared_pip_session(tmp_path: Path) -> Session:
    session: Final[Session] = session_via_cli([
        str(tmp_path / "env"),
        "--seeder",
        "pip",
        "--pip",
        "embed",
        "--no-periodic-update",
    ])
    session.creator.run()
    return session


@pytest.mark.skipif(os.name != "nt", reason="Windows junctions")
def test_pip_reseed_detaches_junction(junction_seed: Path, prepared_pip_session: Session, tmp_path: Path) -> None:
    prepared_pip_session.seeder.run(prepared_pip_session.creator)

    outside: Final[Path] = tmp_path / "outside"
    assert (
        (outside / "REQUESTED").read_bytes(),
        (outside / "other").read_bytes(),
        junction_seed.resolve() == outside,
    ) == (
        b"original",
        b"original",
        False,
    )


@pytest.fixture(params=[pytest.param("root", id="root"), pytest.param("nested", id="nested")])
def junction_seed(request: pytest.FixtureRequest, prepared_pip_session: Session, tmp_path: Path) -> Path:
    outside: Final[Path] = tmp_path / "outside"
    outside.mkdir()
    (outside / "REQUESTED").write_bytes(b"original")
    os.link(outside / "REQUESTED", outside / "other")
    if request.param == "root":
        version: Final[str] = prepared_pip_session.creator.interpreter.version_release_str
        junction: Final[Path] = (
            prepared_pip_session.creator.purelib / f"pip-{get_embed_wheel('pip', version).version}.dist-info"
        )
    else:
        junction = prepared_pip_session.creator.purelib / "pip" / "_internal"
    junction.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(junction), str(outside)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    return junction


@pytest.mark.skipif(not fs_supports_symlink(), reason="symlinks are unavailable")
def test_pip_reseed_replaces_launcher_link(linked_seed: Session) -> None:
    launcher: Final[Path] = linked_seed.creator.script_dir / _LAUNCHER_NAME
    launcher.unlink()
    missing: Final[Path] = linked_seed.creator.dest / "missing-launcher"
    launcher.symlink_to(missing)
    cli_run([str(linked_seed.creator.dest), "--seeder", "pip", "--pip", "embed", "--no-periodic-update"])
    assert (launcher.is_file(), launcher.is_symlink(), missing.exists()) == (True, False, False)


@pytest.mark.parametrize(
    ("invalid", "member", "content"),
    [
        pytest.param("entry", "./", "", id="package-name"),
        pytest.param(
            "script",
            "pip-99.0.dist-info/entry_points.txt",
            "[console_scripts]\n. = pip:main\n",
            id="script-name",
        ),
    ],
)
def test_pip_reseed_rejects_invalid_wheel_names(tmp_path: Path, invalid: str, member: str, content: str) -> None:
    with ZipFile(tmp_path / "pip-99.0-py3-none-any.whl", "w") as archive:
        archive.writestr("pip-99.0.dist-info/METADATA", "Name: pip\nVersion: 99.0\n")
        archive.writestr(member, content)
    with pytest.raises(RuntimeError, match=f"invalid seed wheel {invalid}"):
        cli_run([
            str(tmp_path / "env"),
            "--seeder",
            "pip",
            "--pip",
            "99.0",
            "--extra-search-dir",
            str(tmp_path),
            "--no-download",
            "--no-periodic-update",
        ])


def test_pip_reseed_reports_process_failure(tmp_path: Path, mocker: MockerFixture) -> None:
    process: Final[MockType] = mocker.patch("virtualenv.seed.embed.pip_invoke.Popen", autospec=True)
    process.return_value.configure_mock(returncode=7)
    with pytest.raises(RuntimeError, match="failed seed with code 7"):
        cli_run([str(tmp_path / "env"), "--seeder", "pip", "--pip", "embed", "--no-periodic-update"])


@pytest.mark.skipif(
    sys.platform != "linux" or not hasattr(os, "pidfd_open") or not hasattr(signal, "pidfd_send_signal"),
    reason="requires Linux process descriptors",
)
def test_pip_interrupt_reaps_child_before_temp_cleanup(tmp_path: Path) -> None:
    assert _interrupt_pip_seed(tmp_path) == {"virtualenv_exit": 1, "child_exited": True, "folder_exists": False}


def _interrupt_pip_seed(tmp_path: Path) -> dict[str, int | bool]:
    parent = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "virtualenv",
            "--seeder",
            "pip",
            "--pip",
            "embed",
            "--no-download",
            "--no-periodic-update",
            "--quiet",
            str(tmp_path / "env"),
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    parent_fd = os.pidfd_open(parent.pid)
    child_fd = None
    try:
        deadline = monotonic() + 20
        while monotonic() < deadline:
            assert not select.select([parent_fd], [], [], 0)[0], "virtualenv exited before starting pip"
            for child in Path(f"/proc/{parent.pid}/task/{parent.pid}/children").read_text(encoding="ascii").split():
                try:
                    args = Path(f"/proc/{child}/cmdline").read_bytes().split(b"\0")
                    if b"--find-links" in args:
                        child_fd = os.pidfd_open(int(child))
                        folder = Path(os.fsdecode(args[args.index(b"--find-links") + 1]))
                        break
                except (FileNotFoundError, ProcessLookupError):
                    continue
            if child_fd is not None:
                break
            select.select([parent_fd], [], [], 0.01)
        assert child_fd is not None, "pip child did not start"
        assert not select.select([child_fd], [], [], 0.1)[0], "pip exited before the interrupt"
        parent.send_signal(signal.SIGINT)
        return {
            "virtualenv_exit": parent.wait(timeout=20),
            "child_exited": bool(select.select([child_fd], [], [], 0)[0]),
            "folder_exists": folder.exists(),
        }
    finally:
        parent.kill()
        parent.wait(timeout=5)
        os.close(parent_fd)
        if child_fd is not None:
            if not select.select([child_fd], [], [], 0)[0]:
                signal.pidfd_send_signal(child_fd, signal.SIGTERM)
            os.close(child_fd)


def test_pip_interrupt_reaps_child_after_second_interrupt(tmp_path: Path, mocker: MockerFixture) -> None:
    assert _interrupt_pip_seed_twice(tmp_path, mocker) == {
        "kill_calls": 2,
        "child_exited": True,
        "folder_exists": False,
    }


def _interrupt_pip_seed_twice(tmp_path: Path, mocker: MockerFixture) -> dict[str, int | bool]:
    child: subprocess.Popen[bytes] | None = None
    folder: Path | None = None
    kill_calls = 0

    def start_pip(cmd: list[str], env: dict[str, str]) -> subprocess.Popen[bytes]:
        nonlocal child, folder
        child = subprocess.Popen(cmd, env=env)
        folder = Path(cmd[cmd.index("--find-links") + 1])
        original_kill = child.kill

        def interrupt_kill() -> None:
            nonlocal kill_calls
            kill_calls += 1
            if kill_calls == 1:
                raise KeyboardInterrupt
            original_kill()

        mocker.patch.object(child, "communicate", autospec=True, side_effect=KeyboardInterrupt)
        mocker.patch.object(child, "kill", autospec=True, side_effect=interrupt_kill)
        return child

    mocker.patch("virtualenv.seed.embed.pip_invoke.Popen", autospec=True, side_effect=start_pip)
    try:
        with pytest.raises(KeyboardInterrupt):
            cli_run([str(tmp_path / "env"), "--seeder", "pip", "--pip", "embed", "--no-periodic-update"])
        return {
            "kill_calls": kill_calls,
            "child_exited": child is not None and child.poll() is not None,
            "folder_exists": folder is not None and folder.exists(),
        }
    finally:
        if child is not None and child.poll() is None:
            subprocess.Popen.kill(child)
            child.wait()


@pytest.mark.skipif(
    sys.implementation.name != "cpython" or os.name == "nt", reason="requires CPython POSIX signal tracing"
)
def test_pip_sigint_during_cleanup_entry_reaps_child(tmp_path: Path, mocker: MockerFixture) -> None:
    assert _interrupt_pip_seed_at_cleanup_entry(tmp_path, mocker) == {
        "signals": 1,
        "child_exited": True,
        "folder_exists": False,
    }


def _interrupt_pip_seed_at_cleanup_entry(tmp_path: Path, mocker: MockerFixture) -> dict[str, int | bool]:
    child: subprocess.Popen[bytes] | None = None
    folder: Path | None = None
    signals = 0
    previous_trace = sys.gettrace()

    def send_second_interrupt(frame: FrameType, event: str, _arg: None) -> None:
        nonlocal signals
        if event == "call" and frame.f_code.co_name == "_terminate_pip" and not signals:
            signals += 1
            sys.settrace(previous_trace)
            signal.raise_signal(signal.SIGINT)

    def start_pip(cmd: list[str], env: dict[str, str]) -> subprocess.Popen[bytes]:
        nonlocal child, folder
        child = subprocess.Popen(cmd, env=env)
        folder = Path(cmd[cmd.index("--find-links") + 1])
        mocker.patch.object(child, "communicate", autospec=True, side_effect=KeyboardInterrupt)
        sys.settrace(send_second_interrupt)
        return child

    mocker.patch("virtualenv.seed.embed.pip_invoke.Popen", autospec=True, side_effect=start_pip)
    try:
        with pytest.raises(KeyboardInterrupt):
            cli_run([str(tmp_path / "env"), "--seeder", "pip", "--pip", "embed", "--no-periodic-update"])
        return {
            "signals": signals,
            "child_exited": child is not None and child.poll() is not None,
            "folder_exists": folder is not None and folder.exists(),
        }
    finally:
        sys.settrace(previous_trace)
        if child is not None and child.poll() is None:
            subprocess.Popen.kill(child)
            child.wait()


def test_pip_sigint_after_child_exit_is_reported(tmp_path: Path, mocker: MockerFixture) -> None:
    assert _interrupt_pip_seed_after_child_exit(tmp_path, mocker) == {
        "signal_sent": True,
        "child_exited": True,
        "folder_exists": False,
    }


def _interrupt_pip_seed_after_child_exit(tmp_path: Path, mocker: MockerFixture) -> dict[str, bool]:
    class InterruptedResult:
        def __init__(self, cmd: list[str], env: dict[str, str]) -> None:
            self.child = subprocess.Popen(cmd, env=env)
            self.folder = Path(cmd[cmd.index("--find-links") + 1])
            self.signal_sent = False

        @property
        def returncode(self) -> int | None:
            if not self.signal_sent:
                self.signal_sent = True
                handler = signal.getsignal(signal.SIGINT)
                assert callable(handler)
                handler(signal.SIGINT, None)
            return self.child.returncode

        def communicate(self, timeout: float | None = None) -> tuple[bytes | None, bytes | None]:
            return self.child.communicate(timeout=timeout)

    process: InterruptedResult | None = None

    def start_pip(cmd: list[str], env: dict[str, str]) -> InterruptedResult:
        nonlocal process
        process = InterruptedResult(cmd, env)
        return process

    mocker.patch("virtualenv.seed.embed.pip_invoke.Popen", autospec=True, side_effect=start_pip)
    try:
        with pytest.raises(KeyboardInterrupt):
            cli_run([str(tmp_path / "env"), "--seeder", "pip", "--pip", "embed", "--no-periodic-update"])
        assert process is not None
        return {
            "signal_sent": process.signal_sent,
            "child_exited": process.child.poll() is not None,
            "folder_exists": process.folder.exists(),
        }
    finally:
        if process is not None and process.child.poll() is None:
            process.child.kill()
            process.child.wait()


def test_pip_reseed_reports_missing_wheel(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="could not get wheel for distribution pip"):
        cli_run([str(tmp_path / "env"), "--seeder", "pip", "--pip", "99.1234", "--no-download", "--no-periodic-update"])


@pytest.fixture
def linked_seed(tmp_path: Path, current_fastest: str) -> Session:
    return cli_run([
        str(tmp_path / "env"),
        "--creator",
        current_fastest,
        "--pip",
        "embed",
        "--no-periodic-update",
        "--symlink-app-data",
        "--app-data",
        str(tmp_path / "cache"),
    ])


@pytest.mark.parametrize("safe_path", [pytest.param("", id="default"), pytest.param("1", id="safe-path")])
def test_pip_invoke_uses_selected_wheel(
    tmp_path: Path, current_fastest: str, monkeypatch: pytest.MonkeyPatch, safe_path: str
) -> None:
    monkeypatch.setenv("PYTHONSAFEPATH", safe_path)
    (tmp_path / "pip").mkdir()
    (tmp_path / "pip" / "__init__.py").write_text("raise SystemExit('imported from the working directory')", "utf-8")
    monkeypatch.chdir(tmp_path)
    session: Final[Session] = cli_run([
        str(tmp_path / "env"),
        "--creator",
        current_fastest,
        "--seeder",
        "pip",
        "--pip",
        "embed",
        "--no-periodic-update",
    ])
    result: Final[subprocess.CompletedProcess[str]] = subprocess.run(
        [str(session.creator.exe), "-I", "-m", "pip", "--version"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    assert os.path.normcase(str(session.creator.purelib)) in os.path.normcase(result.stdout)


@pytest.mark.usefixtures("_no_coverage")
def test_pip_invoke_uses_selected_archive_with_configured_links(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    wheel = get_embed_wheel("pip", f"{sys.version_info.major}.{sys.version_info.minor}")
    env_links = tmp_path / "env-links"
    env_links.mkdir()
    config_links = tmp_path / "config-links"
    config_links.mkdir()
    competing_name = wheel.name.replace("-py3-none-any.whl", "-1-py3-none-any.whl")
    copyfile(wheel.path, env_links / competing_name)
    copyfile(wheel.path, config_links / competing_name)
    (tmp_path / "pip.conf").write_text(f"[global]\nfind-links = {config_links}\n", encoding="utf-8")
    monkeypatch.setenv("PIP_FIND_LINKS", str(env_links))
    monkeypatch.setenv("PIP_CONFIG_FILE", str(tmp_path / "pip.conf"))
    monkeypatch.setenv("PIP_REPORT", str(tmp_path / "report.json"))

    cli_run([
        str(tmp_path / "env"),
        "--seeder",
        "pip",
        "--pip",
        "embed",
        "--no-setuptools",
        "--no-periodic-update",
        "--no-download",
    ])

    installed = json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))["install"][0]
    assert (installed["download_info"]["url"].rsplit("/", 1)[-1], installed["is_direct"]) == (wheel.name, False)


@pytest.mark.parametrize(
    ("excluded", "expected"),
    [
        pytest.param(["--no-pip"], {"setuptools"}, id="no-pip"),
        pytest.param(["--no-setuptools"], {"pip"}, id="no-setuptools"),
        pytest.param([], {"pip", "setuptools"}, id="all"),
    ],
)
def test_base_bootstrap_via_pip_invoke(
    tmp_path: Path, current_fastest: str, excluded: list[str], expected: set[str]
) -> None:
    command: Final[list[str]] = [
        "--seeder",
        "pip",
        str(tmp_path / "env"),
        "--download",
        "--creator",
        current_fastest,
        "--pip",
        "embed",
        "--setuptools",
        "embed",
        "--no-periodic-update",
    ]
    session: Final[Session] = cli_run([*command, *excluded])
    assert {path.name for path in session.creator.purelib.iterdir()} & {"pip", "setuptools"} == expected


def test_pip_invoke_runs_pip_for_environment_python(tmp_path: Path, mocker: MockerFixture) -> None:
    session: Final[Session] = session_via_cli([
        str(tmp_path / "env"),
        "--seeder",
        "pip",
        "--no-download",
        "--no-periodic-update",
    ])
    session.creator.run()
    # no other interpreter is needed: report a version whose bundled pip differs from the one of this interpreter
    target: Final[str] = {MIN: MAX}.get(session.creator.interpreter.version_release_str, MIN)
    mocker.patch.object(PythonInfo, "version_release_str", new_callable=mocker.PropertyMock, return_value=target)
    process: Final[MockType] = mocker.patch("virtualenv.seed.embed.pip_invoke.Popen", autospec=True)
    process.return_value.configure_mock(returncode=0)

    session.seeder.run(session.creator)

    assert Path(process.call_args.kwargs["env"]["VIRTUALENV_PIP_WHEEL"]).name == get_embed_wheel("pip", target).name


def test_pip_invoke_reports_unavailable_wheel(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="could not get wheel for distribution pip"):
        cli_run([
            str(tmp_path / "env"),
            "--seeder",
            "pip",
            "--pip",
            "0.0.0",
            "--no-download",
            "--no-periodic-update",
        ])


@pytest.mark.usefixtures("_no_coverage")
def test_pip_invoke_freeze_uses_version_pin(tmp_path: Path) -> None:
    session: Final[Session] = cli_run([
        str(tmp_path / "env"),
        "--seeder",
        "pip",
        "--pip",
        "embed",
        "--no-setuptools",
        "--no-periodic-update",
    ])
    result: Final[subprocess.CompletedProcess[str]] = subprocess.run(
        [str(session.creator.exe), "-I", "-m", "pip", "freeze", "--all"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    version: Final[str] = get_embed_wheel("pip", f"{sys.version_info.major}.{sys.version_info.minor}").version
    assert f"pip=={version}" in result.stdout.splitlines()


@pytest.mark.skipif(os.name == "nt", reason="POSIX launcher rewrite")
def test_pip_invoke_leaves_stale_record_outside_environment(tmp_path: Path) -> None:
    session: Final[Session] = session_via_cli([
        str(tmp_path / "env"),
        "--seeder",
        "pip",
        "--pip",
        "embed",
        "--no-setuptools",
        "--no-periodic-update",
    ])
    session.creator.run()
    outside: Final[Path] = tmp_path / "outside-1.dist-info" / "RECORD"
    outside.parent.mkdir()
    outside.write_text("outside untouched\n", encoding="utf-8")
    tool: Final[Path] = session.creator.script_dir / "stale-tool"
    old_script: Final[bytes] = b"#!/bin/sh\n'''exec' true\n' '''\nprint('stale')\n"
    tool.write_bytes(old_script)
    metadata: Final[Path] = session.creator.purelib / "pip-0.dist-info"
    metadata.mkdir()
    (metadata / "METADATA").write_text("Metadata-Version: 2.1\nName: pip\nVersion: 0\n", encoding="utf-8")
    (metadata / "RECORD").write_text(
        f"{os.path.relpath(tool, session.creator.purelib)},,\n{os.path.relpath(outside, session.creator.purelib)},,\n",
        encoding="utf-8",
    )

    session.seeder.run(session.creator)

    assert (outside.read_text(encoding="utf-8"), tool.read_bytes(), (session.creator.purelib / "pip").is_dir()) == (
        "outside untouched\n",
        old_script,
        True,
    )


@pytest.mark.skipif(not fs_supports_symlink(), reason="symlinks are unavailable")
@pytest.mark.skipif(sys.version_info < (3, 10), reason="requires two compatible bundled pip versions")
def test_pip_reseed_removes_previous_version_metadata(tmp_path: Path) -> None:
    old: Final[str] = BUNDLE_SUPPORT["3.9"]["pip"].split("-")[1]
    session: Final[Session] = cli_run([
        str(tmp_path / "env"),
        "--pip",
        old,
        "--extra-search-dir",
        str(BUNDLE_FOLDER),
        "--symlink-app-data",
        "--no-periodic-update",
        "--app-data",
        str(tmp_path / "cache"),
    ])
    cli_run([str(session.creator.dest), "--seeder", "pip", "--pip", "embed", "--no-periodic-update"])
    expected: Final[str] = BUNDLE_SUPPORT[f"{sys.version_info.major}.{sys.version_info.minor}"]["pip"].split("-")[1]
    assert sorted(entry.name for entry in session.creator.purelib.glob("pip-*.dist-info")) == [
        f"pip-{expected}.dist-info",
    ]
    assert not list(session.creator.purelib.glob(f"pip-{old}.virtualenv"))
