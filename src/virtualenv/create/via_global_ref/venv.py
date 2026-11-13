from __future__ import annotations

import logging
from argparse import ArgumentTypeError
from typing import TYPE_CHECKING, Final

from python_discovery import PythonInfo

from virtualenv.util.error import ProcessCallFailedError
from virtualenv.util.path import ensure_within
from virtualenv.util.subprocess import run_cmd
from virtualenv.util.text import collapse_line_boundaries

from .api import ViaGlobalRefApi, ViaGlobalRefMeta
from .builtin.cpython.common import is_mac_os_framework
from .builtin.cpython.mac_os import CPython3macOsBrew
from .store import handle_store_python

if TYPE_CHECKING:
    from virtualenv.config.cli.parser import VirtualEnvOptions

_LOGGER: Final[logging.Logger] = logging.getLogger(__name__)


class Venv(ViaGlobalRefApi):
    """Create an environment with the stdlib ``venv`` module of the host interpreter.

    Runs inline when the host is the current interpreter, otherwise through a subprocess.

    :param options: the parsed command line options
    :param interpreter: the interpreter the environment is created from

    :var describe: the describer whose attributes stand in for the host interpreter, ``None`` when not describing
    :var can_be_inline: ``True`` when the host is the current interpreter and can create the environment in process

    """

    def __init__(self, options: VirtualEnvOptions, interpreter: PythonInfo) -> None:
        self.describe = options.describe
        super().__init__(options, interpreter)
        current = PythonInfo.current()
        self.can_be_inline = interpreter is current and interpreter.executable == interpreter.system_executable
        self._context = None

    def __getattribute__(
        self, item: str
    ) -> object:  # simplint: ignore[imprecise-annotation]  # proxied attributes differ in type
        if (describe := object.__getattribute__(self, "describe")) is not None and hasattr(describe, item):
            element = getattr(describe, item)
            if not callable(element) or item == "script":
                return element
        return object.__getattribute__(self, item)

    def _args(self) -> list[tuple[str, str | bool]]:
        return super()._args() + ([("describe", self.describe.__class__.__name__)] if self.describe else [])

    @classmethod
    def can_create(cls, interpreter: PythonInfo) -> ViaGlobalRefMeta | None:
        """Allow creation when ``venv`` is available, recording the store and framework limits.

        :param interpreter: the interpreter to check

        :returns: the capability metadata, or ``None`` when the interpreter has no ``venv`` module

        """
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
        """Create the environment, first checking the destination paths stay within it."""
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

    def create_inline(self) -> None:
        """Create the environment with the stdlib ``venv`` module imported in this process."""
        # the stdlib venv module is imported only when this creator runs, to keep startup cheap
        from venv import EnvBuilder  # ruff:ignore[import-outside-top-level]

        builder = EnvBuilder(
            system_site_packages=self.enable_system_site_package,
            clear=False,
            symlinks=self.symlinks,
            with_pip=False,
        )
        builder.create(str(self.dest))

    def create_via_sub_process(self) -> None:
        """Create the environment with the stdlib ``venv`` module of the host interpreter in a subprocess.

        :raises ProcessCallFailedError: when the subprocess exits with a non-zero code

        """
        cmd = self.get_host_create_cmd()
        _LOGGER.info("using host built-in venv to create via %s", " ".join(cmd))
        code, out, err = run_cmd(cmd)
        if code != 0:
            raise ProcessCallFailedError(code, out, err, cmd)

    def get_host_create_cmd(self) -> list[str]:
        """Return the command that creates the environment with the host interpreter's ``venv`` module.

        :returns: the command line, as a list of arguments

        """
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
        # system_executable is optional in PythonInfo, so the command list is list[str | None]
        return cmd  # ty: ignore[invalid-explicit-return]

    @classmethod
    def validate_dest(cls, raw_value: str) -> str:
        """Validate the destination, rejecting line boundaries that the stdlib ``venv`` cannot record.

        :param raw_value: the destination as given on the command line

        :returns: the destination path as a string

        :raises ArgumentTypeError: when the destination contains a line boundary

        """
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

    def set_pyenv_cfg(self) -> None:
        """Record the GraalPy launcher settings in the ``pyvenv.cfg`` file."""
        super().set_pyenv_cfg()
        if self.interpreter.implementation == "GraalPy":
            # GraalPy launchers need these settings on Windows and macOS.
            self.pyenv_cfg["venvlauncher_command"] = self.interpreter.system_exe
            self.pyenv_cfg["base-executable"] = self.interpreter.system_exe


__all__ = [
    "Venv",
]
