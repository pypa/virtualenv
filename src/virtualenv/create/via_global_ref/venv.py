from __future__ import annotations

import logging
from argparse import ArgumentTypeError
from typing import TYPE_CHECKING, Final

from python_discovery import PythonInfo

from virtualenv.create.via_global_ref.store import handle_store_python
from virtualenv.util.error import ProcessCallFailedError
from virtualenv.util.path import ensure_within
from virtualenv.util.subprocess import run_cmd
from virtualenv.util.text import collapse_line_boundaries

from .api import ViaGlobalRefApi, ViaGlobalRefMeta
from .builtin.cpython.common import is_mac_os_framework
from .builtin.cpython.mac_os import CPython3macOsBrew

if TYPE_CHECKING:
    from typing import Any

    from virtualenv.config.cli.parser import VirtualEnvOptions

LOGGER = logging.getLogger(__name__)


class Venv(ViaGlobalRefApi):
    def __init__(self, options: VirtualEnvOptions, interpreter: PythonInfo) -> None:
        self.describe = options.describe
        super().__init__(options, interpreter)
        current = PythonInfo.current()
        self.can_be_inline = interpreter is current and interpreter.executable == interpreter.system_executable
        self._context = None

    def _args(self) -> list[tuple[str, Any]]:
        return super()._args() + ([("describe", self.describe.__class__.__name__)] if self.describe else [])

    @classmethod
    def can_create(cls, interpreter: PythonInfo) -> ViaGlobalRefMeta | None:
        if interpreter.has_venv:
            if CPython3macOsBrew.can_describe(interpreter):
                return CPython3macOsBrew.setup_meta(interpreter)
            meta = ViaGlobalRefMeta()
            if interpreter.platform == "win32":
                meta = handle_store_python(meta, interpreter)
            if is_mac_os_framework(interpreter):
                meta.copy_error = "macOS framework builds do not support copy-based virtual environments"
            return meta
        return None

    def create(self) -> None:
        # stdlib venv writes interpreter files, configuration and activation scripts in place, so a planted symlink or
        # hard link would receive them outside the environment
        for directory in (self.bin_dir, self.purelib, self.platlib):
            ensure_within(self.dest, directory)
        for path in (self.dest / "pyvenv.cfg", self.dest / ".gitignore", *self.bin_dir.iterdir()):
            if path.is_symlink() or (path.is_file() and path.stat().st_nlink > 1):
                path.unlink()
        if self.can_be_inline:
            self.create_inline()
        else:
            self.create_via_sub_process()
        if self.describe is not None:
            self.describe.install_venv_shared_libs(self)
        super().create()

    @classmethod
    def validate_dest(cls, raw_value: str) -> str:
        return cls._check_line_boundaries(super().validate_dest(cls._check_line_boundaries(raw_value)))

    @staticmethod
    def _check_line_boundaries(value: str) -> str:
        # stdlib venv writes the destination into pyvenv.cfg without escaping line boundaries.
        if collapse_line_boundaries(value) != value:
            msg: Final = (
                f"destination {value!r} must not contain a line boundary as venv cannot record it in pyvenv.cfg"
            )
            raise ArgumentTypeError(msg)
        return value

    def create_inline(self) -> None:
        from venv import EnvBuilder  # ruff:ignore[import-outside-top-level]

        builder = EnvBuilder(
            system_site_packages=self.enable_system_site_package,
            clear=False,
            symlinks=self.symlinks,
            with_pip=False,
        )
        builder.create(str(self.dest))

    def create_via_sub_process(self) -> None:
        cmd = self.get_host_create_cmd()
        LOGGER.info("using host built-in venv to create via %s", " ".join(cmd))
        code, out, err = run_cmd(cmd)
        if code != 0:
            raise ProcessCallFailedError(code, out, err, cmd)

    def get_host_create_cmd(self) -> list[str]:
        cmd = [
            self.interpreter.system_executable,
            "-c",
            (
                "import sys; sys.path[:] = [p for p in sys.path if p != '']; "
                "import runpy; runpy.run_module('venv', run_name='__main__', alter_sys=True)"
            ),
            "--without-pip",
        ]
        if self.interpreter.version_info >= (3, 13):
            cmd.append("--without-scm-ignore-files")
        if self.enable_system_site_package:
            cmd.append("--system-site-packages")
        cmd.extend(("--symlinks" if self.symlinks else "--copies", str(self.dest)))
        return cmd  # ty: ignore[invalid-return-type]

    def set_pyenv_cfg(self) -> None:
        super().set_pyenv_cfg()
        if self.interpreter.implementation == "GraalPy":
            # GraalPy launchers need these settings on Windows and macOS.
            self.pyenv_cfg["venvlauncher_command"] = self.interpreter.system_exe
            self.pyenv_cfg["base-executable"] = self.interpreter.system_exe

    def __getattribute__(self, item: str) -> object:
        describe = object.__getattribute__(self, "describe")
        if describe is not None and hasattr(describe, item):
            element = getattr(describe, item)
            if not callable(element) or item == "script":
                return element
        return object.__getattribute__(self, item)


__all__ = [
    "Venv",
]
