from __future__ import annotations

import sys
from typing import TYPE_CHECKING, Final

import pytest
from python_discovery import PythonInfo

from virtualenv.create.via_global_ref.builtin.cpython.common import is_mac_os_framework, is_macos_brew
from virtualenv.info import IS_WIN, fs_supports_symlink
from virtualenv.run import cli_run
from virtualenv.util.path import copy, symlink

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path


@pytest.mark.skipif(not fs_supports_symlink(), reason="symlink is not supported")
@pytest.mark.parametrize("operation", [pytest.param(copy, id="copy"), pytest.param(symlink, id="symlink")])
@pytest.mark.parametrize("directory", [pytest.param(False, id="file"), pytest.param(True, id="directory")])
@pytest.mark.parametrize("loop", [pytest.param(False, id="missing-target"), pytest.param(True, id="self-loop")])
def test_replace_dangling_symlink(
    tmp_path: Path, operation: Callable[[Path, Path], None], directory: bool, loop: bool
) -> None:
    source: Final[Path] = tmp_path / "source"
    if directory:
        source.mkdir()
    (source / "file.txt" if directory else source).write_text("new", encoding="utf-8")
    destination: Final[Path] = tmp_path / "destination"
    outside: Final[Path] = tmp_path / "outside"
    destination.symlink_to(destination if loop else outside, target_is_directory=directory)

    operation(source, destination)

    assert (
        destination.is_symlink(),
        (destination / "file.txt" if directory else destination).read_text(encoding="utf-8"),
        destination.resolve(),
        outside.exists(),
    ) == (operation is symlink, "new", source.resolve() if operation is symlink else destination, False)


@pytest.mark.skipif(IS_WIN or not fs_supports_symlink(), reason="requires POSIX interpreter aliases")
@pytest.mark.parametrize(
    "mode",
    [
        pytest.param(
            "--copies",
            id="copy",
            marks=pytest.mark.skipif(
                is_macos_brew(PythonInfo.current_system()) or is_mac_os_framework(PythonInfo.current_system()),
                reason="Homebrew and framework builds require symlinks",
            ),
        ),
        pytest.param("--symlinks", id="symlink"),
    ],
)
def test_recreate_environment_with_dangling_alias(tmp_path: Path, mode: str) -> None:
    destination: Final[Path] = tmp_path / "venv"
    cli_run([str(destination), "--creator", "builtin", "--no-seed", "--symlinks"])
    alias: Final[Path] = destination / "bin" / f"python{sys.version_info.major}"
    alias.unlink()
    outside: Final[Path] = tmp_path / "removed-python"
    alias.symlink_to(outside)

    cli_run([str(destination), "--creator", "builtin", "--no-seed", mode])

    assert (alias.is_symlink(), alias.is_file(), outside.exists()) == (mode == "--symlinks", True, False)
