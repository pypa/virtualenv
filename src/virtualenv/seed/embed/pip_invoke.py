from __future__ import annotations

import csv
import hashlib
import io
import logging
import os
from base64 import urlsafe_b64encode
from contextlib import contextmanager
from importlib.metadata import distributions
from pathlib import Path
from shutil import copyfile
from stat import S_IMODE
from subprocess import Popen
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING, Final
from zipfile import ZipFile

from virtualenv.seed.embed.base_embed import BaseEmbed
from virtualenv.seed.embed.via_app_data.pip_install.base import EntryPointConfig, shell_shebang
from virtualenv.seed.wheels import get_wheel, pip_wheel_env_run
from virtualenv.seed.wheels.acquire import PIP_RUN
from virtualenv.seed.wheels.util import Version
from virtualenv.util.subprocess import LogCmd

if TYPE_CHECKING:
    from collections.abc import Generator

    from virtualenv.config.cli.parser import VirtualEnvOptions
    from virtualenv.create.creator import Creator


class PipInvoke(BaseEmbed):
    def __init__(self, options: VirtualEnvOptions) -> None:
        super().__init__(options)
        self._wheels: list[Path] = []

    def run(self, creator: Creator) -> None:
        if not self.enabled:
            return
        with self.get_pip_install_cmd(creator.exe, creator.interpreter.version_release_str) as cmd:
            self._detach_links(creator)
            self._execute(cmd, pip_wheel_env_run(self.extra_search_dir, self.app_data, self.env))
        if os.name == "posix":
            self._rewrite_launchers(creator)

    def _rewrite_launchers(self, creator: Creator) -> None:
        selected: Final = self.distribution_to_versions()
        exe: Final = str(creator.exe).encode("utf-8")
        for distribution in distributions(path=sorted({str(creator.purelib), str(creator.platlib)})):
            if distribution.metadata["Name"].lower().replace("-", "_") not in selected:
                continue
            rows: Final = list(csv.reader(io.StringIO(distribution.read_text("RECORD") or "")))
            changed = False
            for row in rows:
                path: Final = Path(os.path.abspath(str(distribution.locate_file(row[0]))))
                if path.parent != creator.script_dir or not path.is_file():
                    continue
                content = path.read_bytes()
                if content.startswith(b"#!/bin/sh\n'''exec' "):
                    body = content.split(b"\n", 3)[3]
                elif content.startswith(b"#!" + exe + b"\n") and len(exe.split()) > 1:
                    body = content.split(b"\n", 1)[1]
                else:
                    continue
                content = shell_shebang(str(creator.exe)) + body
                mode: Final = S_IMODE(path.stat().st_mode) & 0o755
                path.unlink()
                with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode), "wb") as stream:
                    stream.write(content)
                row[1:] = [
                    "sha256=" + urlsafe_b64encode(hashlib.sha256(content).digest()).rstrip(b"=").decode("ascii"),
                    str(len(content)),
                ]
                changed = True
            if changed:
                record: Final = next(row[0] for row in rows if row[0].endswith(".dist-info/RECORD"))
                with Path(str(distribution.locate_file(record))).open("w", encoding="utf-8", newline="") as stream:
                    csv.writer(stream).writerows(rows)

    @contextmanager
    def get_pip_install_cmd(self, exe: Path, for_py_version: str) -> Generator[list[str], None, None]:
        self._wheels.clear()
        cmd: Final = [
            str(exe),
            "-c",
            PIP_RUN,
            "-q",
            "install",
            "--only-binary",
            ":all:",
            "--disable-pip-version-check",
            "--ignore-installed",
            "--no-index",
        ]
        # Only the selected archives may participate in pip's filename-based selection.
        with TemporaryDirectory(prefix="virtualenv-seed-") as folder:
            cmd.extend(["--find-links", folder])
            for dist, version in self.distribution_to_versions().items():
                wheel: Final = get_wheel(
                    distribution=dist,
                    version=version,
                    for_py_version=for_py_version,
                    search_dirs=self.extra_search_dir,
                    download=self.download,
                    app_data=self.app_data,
                    do_periodic_update=self.periodic_update,
                    env=self.env,
                )
                if wheel is None:
                    msg: Final = f"could not get wheel for distribution {dist}"
                    raise RuntimeError(msg)
                self._wheels.append(wheel.path)
                copyfile(wheel.path, Path(folder) / wheel.name)
                cmd.append(Version.as_pip_req(dist, wheel.version))
            yield cmd

    def _detach_links(self, creator: Creator) -> None:
        for wheel in self._wheels:
            with ZipFile(wheel) as archive:
                names: Final = archive.namelist()
                for root in {creator.purelib, creator.platlib}:
                    for name in {entry.partition("/")[0] for entry in names}:
                        if Path(name).name != name or name in {"", ".", ".."}:
                            msg: Final = f"invalid seed wheel entry {name!r}"
                            raise RuntimeError(msg)
                        self._detach_tree(root / name)
                for name in names:
                    if name.endswith(".dist-info/entry_points.txt"):
                        self._detach_entry_points(creator, archive.read(name).decode("utf-8"))

        self._detach_metadata(creator)

    def _detach_metadata(self, creator: Creator) -> None:
        for root in {creator.purelib, creator.platlib}:
            for distribution in self.distribution_to_versions():
                for entry in root.glob(f"{distribution.replace('-', '_')}-*"):
                    if entry.suffix in {".dist-info", ".virtualenv"} and entry.is_symlink():
                        entry.unlink()

    @staticmethod
    def _detach_tree(path: Path) -> None:
        if path.is_symlink():
            path.unlink()
        elif path.is_dir():
            for root, dirs, files in os.walk(path, followlinks=False):
                for name in [*dirs, *files]:
                    if (entry := Path(root) / name).is_symlink():
                        entry.unlink()

    def _detach_entry_points(self, creator: Creator, content: str) -> None:
        entries: Final = EntryPointConfig(interpolation=None, strict=False)
        entries.read_string(content)
        for section in ("console_scripts", "gui_scripts"):
            if entries.has_section(section):
                for script in entries[section]:
                    self._detach_script(creator, script)

    @staticmethod
    def _detach_script(creator: Creator, name: str) -> None:
        if Path(name).name != name or name in {"", ".", ".."}:
            msg: Final = f"invalid seed wheel script {name!r}"
            raise RuntimeError(msg)
        scripts: Final = {name}
        if name == "pip" or (name.startswith("pip") and name[3:4].isdigit()):
            scripts.update({
                "pip",
                f"pip{creator.interpreter.version_info.major}",
                f"pip{creator.interpreter.version_info.major}.{creator.interpreter.version_info.minor}",
            })
        for script in scripts:
            for suffix in (".exe", "-script.py", "-script.pyw") if os.name == "nt" else ("",):
                if (path := creator.script_dir / f"{script}{suffix}").is_symlink():
                    path.unlink()

    @staticmethod
    def _execute(cmd: list[str], env: dict[str, str]) -> Popen[bytes]:
        logging.getLogger(__name__).debug("pip seed by running: %s", LogCmd(cmd, env))
        process: Final = Popen(cmd, env=env)
        process.communicate()
        if process.returncode != 0:
            msg: Final = f"failed seed with code {process.returncode}"
            raise RuntimeError(msg)
        return process


__all__ = [
    "PipInvoke",
]
