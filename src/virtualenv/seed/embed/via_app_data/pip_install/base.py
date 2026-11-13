from __future__ import annotations

import logging
import os
import re
import shlex
import zipfile
from abc import ABC, abstractmethod
from configparser import ConfigParser
from contextlib import suppress
from itertools import chain
from pathlib import Path
from tempfile import mkdtemp
from typing import TYPE_CHECKING, Final

from distlib.scripts import ScriptMaker, enquote_executable

from virtualenv.util.path import remove_file, safe_delete

from ._safe_extract_zip import extract_zip as _safe_extract_zip

if TYPE_CHECKING:
    from virtualenv.create.creator import Creator

_LOGGER: Final[logging.Logger] = logging.getLogger(__name__)


_MATCH_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"""
                        (?P<name>[^\W\d]\w*?)  # the script name, which starts with a letter
                        -?\d+(?:\.\d+)*        # an optional dash and the version
                        """,
    re.VERBOSE,
)


class PipInstall(ABC):
    """Install one seed package from a wheel into the environment, using a cached image of the wheel.

    :param wheel: the wheel to install
    :param creator: the creator of the environment
    :param image_folder: the folder holding the cached image of the wheel

    """

    def __init__(self, wheel: Path, creator: Creator, image_folder: Path) -> None:
        self._wheel = wheel
        self._creator = creator
        self._image_dir = image_folder

    def install(self, version_info: tuple[int, ...]) -> None:
        """Install the package, replacing any previous version and creating its console scripts.

        :param version_info: the version of the Python interpreter the package is installed for

        """
        dist_info: Final = self._find_dist_info(self._image_dir)
        self._uninstall_previous_version(dist_info)
        # sync image
        for filename in self._image_dir.iterdir():
            self._sync(filename, self._creator.purelib / filename.name)
        # generate console executables
        consoles = set()
        script_dir = self._creator.script_dir
        for name, module in self._read_console_scripts(dist_info).items():
            consoles.update(self._create_console_entry_point(name, module, script_dir, version_info))
        _LOGGER.debug("generated console scripts %s", " ".join(i.name for i in consoles))

    @staticmethod
    def _find_dist_info(folder: Path) -> Path:
        files = []
        for filename in folder.iterdir():
            files.append(filename.name)
            if filename.suffix == ".dist-info":
                return filename
        msg = f"no .dist-info at {folder}, has {', '.join(files)}"
        raise RuntimeError(msg)

    def _uninstall_previous_version(self, dist_info: Path) -> None:
        dist_name = dist_info.stem.split("-")[0]
        in_folders = chain.from_iterable([i.iterdir() for i in (self._creator.purelib, self._creator.platlib)])
        paths = (p for p in in_folders if p.stem.split("-")[0] == dist_name and p.suffix == ".dist-info" and p.is_dir())
        if (existing_dist := next(paths, None)) is not None:
            self._uninstall_dist(existing_dist, self._creator.dest)

    @staticmethod
    def _uninstall_dist(dist: Path, env_dir: Path) -> None:
        dist_base: Final = dist.parent
        _LOGGER.debug("uninstall existing distribution %s from %s", dist.stem, dist_base)

        top_txt: Final = dist / "top_level.txt"
        paths: Final = (
            {dist.parent / i.strip() for i in top_txt.read_text(encoding="utf-8").splitlines()}
            if top_txt.exists()
            else set()
        )
        paths.add(dist)

        base_dirs: Final = paths.copy()
        record: Final = dist / "RECORD"
        for name in (
            (i.split(",")[0] for i in record.read_text(encoding="utf-8").splitlines()) if record.exists() else ()
        ):
            path: Final = dist_base / name
            if not any(p in base_dirs for p in path.parents):
                paths.add(path)

        root: Final = env_dir.resolve()
        metadata_parents: Final = set(dist.resolve().parents)
        for entry in sorted(paths):
            if entry.exists() or entry.is_symlink():
                linked: Final = entry.is_symlink()
                # Unlinking the final link leaves its target intact; parent links still affect containment.
                resolved: Final = entry.parent.resolve() / entry.name if linked else entry.resolve()
                if root not in resolved.parents or resolved in metadata_parents:
                    _LOGGER.warning(
                        "skip removal of %s listed by %s: not inside environment %s or a parent of the metadata",
                        entry,
                        dist.name,
                        root,
                    )
                elif entry.is_dir() and not linked:
                    safe_delete(entry)
                else:
                    remove_file(entry)

    @abstractmethod
    def _sync(self, src: Path, dst: Path) -> None:
        raise NotImplementedError

    @staticmethod
    def _read_console_scripts(dist_info: Path) -> dict[str, str]:
        scripts: Final[dict[str, str]] = {}
        entry_points = dist_info / "entry_points.txt"
        if entry_points.exists():
            parser = EntryPointConfig(interpolation=None, strict=False)
            with entry_points.open(encoding="utf-8") as file_handler:
                parser.read_file(file_handler)
            if "console_scripts" in parser.sections():
                for name, value in parser.items("console_scripts"):
                    # fold only a trailing version (pip3, pip-3.13), so python3-config and 2to3 keep their names
                    match = _MATCH_PATTERN.fullmatch(name)
                    scripts[match.group("name") if match else name] = value
        return scripts

    def _create_console_entry_point(
        self, name: str, value: str, to_folder: Path, version_info: tuple[int, ...]
    ) -> list[Path]:
        new_files = _ScriptMakerCustom(to_folder, version_info, self._creator.exe, name).make(f"{name} = {value}")
        result = []
        result.extend(Path(i) for i in new_files)
        return result

    def build_image(self) -> None:
        """Extract the seed wheel into a staging directory, fix up its RECORD file, then move it into place.

        Each archive entry is validated before extraction so a tampered wheel cannot escape the image directory via an
        absolute path or ``..`` traversal. Later runs reuse any image directory they find, so it only appears once the
        image is complete: a build that fails part way, for example on a full disk or a path that is too long, removes
        its staging directory, and the next build removes one that a killed process left behind.

        :raises RuntimeError: if the wheel contains an entry that would land outside the image directory.

        """
        # beside the installer folder the staging path is exactly as long as the image path, so the Windows path length
        # limits hit the build the same way they would hit the image
        staging: Final = self._image_dir.parent.with_name(f"{self._image_dir.parent.name}-{self._image_dir.name}")
        if staging.exists():
            safe_delete(staging)
        self._image_dir.parent.mkdir(parents=True, exist_ok=True)
        staging.mkdir()
        with zipfile.ZipFile(str(self._wheel)) as zip_ref:
            folder: Final = self._short_path_if_needed(zip_ref, staging)
            try:
                self._populate_image(zip_ref, folder)
                # keep the short path Windows may have switched to, the install reads through it
                built: Final = folder.parent / self._image_dir.parent.name / self._image_dir.name
                with suppress(FileNotFoundError):
                    built.rmdir()  # an empty image directory counts as missing, but blocks the rename on Windows
                os.replace(folder, built)
            except BaseException:
                safe_delete(folder)
                raise
        self._image_dir = built

    @staticmethod
    def _short_path_if_needed(zip_ref: zipfile.ZipFile, folder: Path) -> Path:
        if os.name != "nt":
            return folder
        # https://docs.microsoft.com/en-us/windows/win32/fileio/maximum-file-path-limitation
        if max(len(i) for i in zip_ref.namelist()) + len(str(folder)) <= 260:  # ruff:ignore[magic-value-comparison]
            return folder
        # deferred, only the path-length fallback needs the short-path helper
        from virtualenv.util.path import get_short_path_name  # ruff:ignore[import-outside-top-level]

        return Path(get_short_path_name(str(folder)))

    def _populate_image(self, zip_ref: zipfile.ZipFile, folder: Path) -> None:
        _LOGGER.debug("build install image for %s to %s", self._wheel.name, folder)
        _safe_extract_zip(zip_ref, folder)
        dist_info: Final = self._find_dist_info(folder)
        self._fix_records(folder, dist_info, self._generate_new_files(folder, dist_info))

    @abstractmethod
    def _fix_records(self, folder: Path, dist_info: Path, extra_record_data: set[Path]) -> None:
        raise NotImplementedError

    def _generate_new_files(self, folder: Path, dist_info: Path) -> set[Path]:
        new_files = set()
        installer = dist_info / "INSTALLER"
        installer.write_text("pip\n", encoding="utf-8")
        new_files.add(installer)
        # inject a no-op root element, as workaround for bug in https://github.com/pypa/pip/issues/7226
        marker = folder / f"{dist_info.stem}.virtualenv"
        marker.write_text("", encoding="utf-8")
        new_files.add(marker)
        to_folder: Final = Path(mkdtemp())
        try:
            rel = os.path.relpath(str(self._creator.script_dir), str(self._creator.purelib))
            version_info = self._creator.interpreter.version_info
            for name, module in self._read_console_scripts(dist_info).items():
                new_files.update(
                    Path(os.path.normpath(str(folder / rel / i.name)))
                    # version_info is a VersionInfo, which the helper types as a plain tuple
                    for i in self._create_console_entry_point(name, module, to_folder, version_info)  # ty: ignore[invalid-argument-type]
                )
        finally:
            safe_delete(to_folder)
        return new_files

    @staticmethod
    def _records_text(folder: Path, files: set[Path] | list[Path]) -> str:
        return "\n".join(f"{os.path.relpath(str(rec), str(folder))},," for rec in files)

    def clear(self) -> None:
        """Remove the cached image of the wheel."""
        if self._image_dir.exists():
            safe_delete(self._image_dir)

    def has_image(self) -> bool:
        """Whether the cached image of the wheel exists and holds files.

        :returns: ``True`` when the image has content

        """
        return self._image_dir.exists() and any(self._image_dir.iterdir())


class EntryPointConfig(ConfigParser):
    """Config parser that keeps the option names as written, without lower-casing them."""

    @staticmethod
    def optionxform(optionstr: str) -> str:
        """Keep the option name as written.

        :param optionstr: the option name

        :returns: the option name unchanged

        """
        return optionstr


class _ScriptMakerCustom(ScriptMaker):
    """Writes the entry point scripts of a distribution, replacing any existing file of the same name.

    :param target_dir: the directory the scripts are written to
    :param version_info: the interpreter version, with ``major`` and ``minor``
    :param executable: the interpreter the scripts run with
    :param name: the name of the script

    :var clobber: ``True`` so existing scripts are overwritten
    :var set_mode: ``True`` so the scripts are made executable
    :var variants: the script variants to write, inherited from ``ScriptMaker``

    """  # simplint: ignore[function-docstring]  # existing public docs

    def __init__(self, target_dir: Path, version_info: tuple[int, ...], executable: Path, name: str) -> None:
        super().__init__(None, str(target_dir))
        self.clobber = True  # overwrite
        self.set_mode = True  # ensure they are executable
        self.executable = enquote_executable(str(executable))
        # callers pass a VersionInfo with .major and .minor, the parameter is typed as tuple
        self.version_info = version_info.major, version_info.minor  # ty: ignore[missing-attribute]
        self.variants = {"", "X", "X.Y"}
        self._name = name
        self._raw_executable = str(executable)

    def _build_shebang(self, executable: bytes, post_interp: bytes) -> bytes:
        shebang: Final = super()._build_shebang(executable, post_interp)
        if os.name != "posix" or len(shebang.split()) == 1:
            return shebang
        return shell_shebang(self._raw_executable, post_interp)

    def _write_script(
        self, names: set[str], shebang: bytes, script_bytes: bytes, filenames: list[str], ext: str
    ) -> None:
        names.add(f"{self._name}{self.version_info[0]}.{self.version_info[1]}")
        for name in names:
            path: Final = Path(self.target_dir) / (f"{name}.exe" if os.name == "nt" else name)
            if path.is_symlink():
                path.unlink()
        super()._write_script(names, shebang, script_bytes, filenames, ext)


def shell_shebang(executable: str, post_interp: bytes = b"") -> bytes:
    # The exec line is read by both sh and Python; double-quoted backslashes survive both readers.
    """Build a shebang that runs the executable through ``sh`` and then Python.

    :param executable: the executable to run
    :param post_interp: the bytes appended after the interpreter path

    :returns: the shebang and the wrapper lines, as bytes

    """
    quoted: Final = shlex.quote(executable).replace("\\", "'\"\\\\\"'")
    return b"#!/bin/sh\n'''exec' " + quoted.encode("utf-8") + post_interp + b' "$0" "$@"\n' + b"' '''\n"


__all__ = [
    "EntryPointConfig",
    "PipInstall",
    "shell_shebang",
]
