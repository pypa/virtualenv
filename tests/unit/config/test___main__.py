from __future__ import annotations

import os
import re
import runpy
import shutil
import sys
from importlib.metadata import distribution
from pathlib import Path
from subprocess import check_output
from types import MappingProxyType
from typing import TYPE_CHECKING, Final, NoReturn

import pytest

import virtualenv
from virtualenv.__main__ import run_with_catch
from virtualenv.util.error import ProcessCallFailedError

if TYPE_CHECKING:
    from collections.abc import Callable


@pytest.fixture
def module_entry_version(monkeypatch: pytest.MonkeyPatch) -> Callable[[], int]:
    monkeypatch.setattr(sys, "argv", ["virtualenv", "--version"])
    # runpy warns when the module it is about to execute is already imported
    monkeypatch.delitem(sys.modules, "virtualenv.__main__")

    def run() -> int:
        with pytest.raises(SystemExit) as context:
            runpy.run_module("virtualenv", run_name="__main__")
        return context.value.code

    return run


def test_module_entry_removes_implicit_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, module_entry_version: Callable[[], int]
) -> None:
    monkeypatch.chdir(tmp_path)
    original: Final = sys.path.copy()
    monkeypatch.setattr(sys, "path", [str(tmp_path), *original])
    assert (module_entry_version(), sys.path) == (0, original)


def test_module_entry_keeps_other_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, module_entry_version: Callable[[], int]
) -> None:
    monkeypatch.chdir(tmp_path)
    original: Final = sys.path.copy()
    monkeypatch.setattr(sys, "path", [str(tmp_path / "other"), *original])
    assert (module_entry_version(), sys.path) == (0, [str(tmp_path / "other"), *original])


@pytest.mark.skipif(os.name == "nt", reason="Windows keeps the working directory open")
def test_module_entry_without_working_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, module_entry_version: Callable[[], int]
) -> None:
    directory: Final = tmp_path / "removed"
    directory.mkdir()
    monkeypatch.chdir(directory)
    directory.rmdir()
    assert module_entry_version() == 0


@pytest.fixture
def raise_on_session_done(mocker):
    def _func(exception) -> None:
        # imported inside the helper, so the module loads only when the helper runs
        from virtualenv.run import session_via_cli  # ruff:ignore[import-outside-top-level]

        prev_session = session_via_cli

        def _session_via_cli(args, options=None, setup_logging=True, env=None) -> NoReturn:
            prev_session(args, options, setup_logging, env)
            raise exception

        mocker.patch("virtualenv.run.session_via_cli", side_effect=_session_via_cli, autospec=True)

    return _func


def test_fail_no_traceback(raise_on_session_done, tmp_path, capsys) -> None:
    raise_on_session_done(ProcessCallFailedError(code=2, out="out\n", err="err\n", cmd=["something"]))
    with pytest.raises(SystemExit) as context:
        run_with_catch([str(tmp_path)])
    assert context.value.code == 2
    out, err = capsys.readouterr()
    assert out == f"subprocess call failed for [{'something'!r}] with code 2\nout\nSystemExit: 2\n"
    assert err == "err\n"


def test_discovery_fails_no_discovery_plugin(mocker, tmp_path, capsys) -> None:
    mocker.patch("virtualenv.run.plugin.discovery.Discovery.entry_points_for", return_value={}, autospec=True)
    with pytest.raises(SystemExit) as context:
        run_with_catch([str(tmp_path)])
    assert context.value.code == 1
    out, err = capsys.readouterr()
    assert "RuntimeError: No discovery plugin found. Try reinstalling virtualenv to fix this issue." in out
    assert not err


def test_fail_with_traceback(raise_on_session_done, tmp_path, capsys) -> None:
    raise_on_session_done(TypeError("something bad"))

    with pytest.raises(TypeError, match="something bad"):
        run_with_catch([str(tmp_path), "--with-traceback"])
    out, err = capsys.readouterr()
    assert not out
    assert not err


@pytest.mark.usefixtures("session_app_data")
def test_session_report_full(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    run_with_catch([str(tmp_path), "--setuptools", "bundle"])
    out, err = capsys.readouterr()
    assert not err
    lines = out.splitlines()
    regexes = [
        r"created virtual environment .* in \d+ms",
        r"  creator .*",
        r"  seeder .*",
        r"    added seed packages: .*pip==.*, setuptools==.*",
        r"  activators .*",
    ]
    _match_regexes(lines, regexes)


def _match_regexes(lines, regexes) -> None:
    for line, regex in zip(lines, regexes):
        comp_regex = re.compile(rf"^{regex}$")
        assert comp_regex.match(line), line


@pytest.mark.usefixtures("session_app_data")
def test_session_report_minimal(tmp_path, capsys) -> None:
    run_with_catch([str(tmp_path), "--activators", "", "--without-pip"])
    out, err = capsys.readouterr()
    assert not err
    lines = out.splitlines()
    regexes = [
        r"created virtual environment .* in \d+ms",
        r"  creator .*",
    ]
    _match_regexes(lines, regexes)


@pytest.mark.usefixtures("session_app_data")
def test_session_report_subprocess(tmp_path) -> None:
    # when called via a subprocess the logging framework should flush and POSIX line normalization happen
    out = check_output(
        [sys.executable, "-m", "virtualenv", str(tmp_path), "--activators", "powershell", "--without-pip"],
        text=True,
        encoding="utf-8",
    )
    lines = out.split("\n")
    regexes = [
        r"created virtual environment .* in \d+ms",
        r"  creator .*",
        r"  activators .*",
    ]
    _match_regexes(lines, regexes)


_COPY_BY_KIND: Final[MappingProxyType[bool, Callable[[Path, Path], object]]] = MappingProxyType({
    True: shutil.copytree,
    False: shutil.copy2,
})


def test_module_entry_from_target_install(tmp_path: Path) -> None:
    _create_env_from_target(tmp_path, _copy_target_install(tmp_path), flags=[], pythonpath="")


def _create_env_from_target(tmp_path: Path, target: Path, flags: list[str], pythonpath: str) -> None:
    # venv from inside a virtualenv on 3.10 and earlier records the virtualenv as home, which only works where the
    # interpreter's compiled-in prefix exists
    bare: Final = tmp_path / "bare"
    check_output([sys.executable, "-m", "virtualenv", str(bare), "--no-seed", "--activators="])
    executable: Final = bare / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    check_output(
        [str(executable), *flags, "-m", "virtualenv", str(tmp_path / "env"), "--no-seed", "--activators="],
        cwd=target,
        env={**os.environ, "PYTHONPATH": pythonpath},
        text=True,
        encoding="utf-8",
    )
    assert (tmp_path / "env" / "pyvenv.cfg").is_file()


def _copy_target_install(tmp_path: Path) -> Path:
    target: Final = tmp_path / "target"
    target.mkdir()
    shutil.copytree(Path(virtualenv.__file__).parent, target / "virtualenv")
    copied: Final[set[str]] = {"virtualenv"}
    for name in (
        "virtualenv",
        "distlib",
        "filelock",
        "platformdirs",
        "packaging",
        "python-discovery",
        *(("typing-extensions",) if sys.version_info < (3, 11) else ()),
    ):
        metadata = distribution(name)
        roots = {file.parts[0] for file in metadata.files or () if file.parts[0] not in {"..", "__pycache__"}}
        for root in roots - copied:
            source = Path(str(metadata.locate_file(root)))
            _COPY_BY_KIND[source.is_dir()](source, target / root)
        copied |= roots
    return target


@pytest.mark.skipif(sys.version_info < (3, 11), reason="requires -P")
def test_module_entry_from_target_install_safe_path(tmp_path: Path) -> None:
    target: Final = _copy_target_install(tmp_path)
    # with only the metadata left in the working directory, dropping that explicit entry loses the discovery plugin
    library: Final = tmp_path / "library"
    library.mkdir()
    (target / "virtualenv").rename(library / "virtualenv")
    _create_env_from_target(tmp_path, target, flags=["-P"], pythonpath=os.pathsep.join(map(str, [target, library])))
