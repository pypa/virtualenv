"""Bootstrap."""

from __future__ import annotations

import logging
import sys
import traceback
from contextlib import contextmanager
from pathlib import Path
from subprocess import CalledProcessError
from threading import Lock, Thread
from typing import TYPE_CHECKING, Final

from virtualenv.info import fs_supports_symlink
from virtualenv.seed.embed.base_embed import BaseEmbed
from virtualenv.seed.wheels import get_wheel

from .pip_install.copy import CopyPipInstall
from .pip_install.symlink import SymlinkPipInstall

if TYPE_CHECKING:
    from argparse import ArgumentParser
    from collections.abc import Generator

    from python_discovery import PythonInfo

    from virtualenv.app_data.base import AppData
    from virtualenv.config.cli.parser import VirtualEnvOptions
    from virtualenv.create.creator import Creator
    from virtualenv.seed.wheels.util import Wheel
    from virtualenv.util.lock import PathLockBase

    from .pip_install.base import PipInstall

LOGGER: Final[logging.Logger] = logging.getLogger(__name__)


class FromAppData(BaseEmbed):
    """Seeder that installs the seed packages from wheel images cached in the application data folder.

    :param options: the parsed options

    :var symlinks: ``True`` to symlink the packages from the cached images instead of copying them

    """

    def __init__(self, options: VirtualEnvOptions) -> None:
        super().__init__(options)
        # env var and config file values skip the gate on the CLI flag, so apply it here too
        self.symlinks = options.symlink_app_data and self._can_symlink(self.app_data)
        if options.symlink_app_data and self.app_data.transient:
            LOGGER.debug("copy seed packages because temporary app-data is removed after creation")
        elif options.symlink_app_data and not self.symlinks:
            LOGGER.debug("copy seed packages because the filesystem does not support symlinks")

    @staticmethod
    def _can_symlink(app_data: AppData) -> bool:
        return app_data.transient is False and fs_supports_symlink()

    def __repr__(self) -> str:
        msg = f", via={'symlink' if self.symlinks else 'copy'}, app_data_dir={self.app_data}"
        base = super().__repr__()
        return f"{base[:-1]}{msg}{base[-1]}"

    @classmethod
    def add_parser_arguments(cls, parser: ArgumentParser, interpreter: PythonInfo, app_data: AppData) -> None:
        """Add the option that symlinks the packages from the application data folder, when the platform supports it.

        :param parser: the parser to add the option to
        :param interpreter: the interpreter the environment is created from
        :param app_data: the application data folder

        """
        super().add_parser_arguments(parser, interpreter, app_data)
        can_symlink = cls._can_symlink(app_data)
        sym = "" if can_symlink else "not supported - "
        parser.add_argument(
            "--symlink-app-data",
            dest="symlink_app_data",
            action="store_true" if can_symlink else "store_false",
            help=f"{sym} symlink the python packages from the app-data folder (requires seed pip>=19.3)",
            default=False,
        )

    def run(self, creator: Creator) -> None:
        """Install the seed packages into the environment from the cached images.

        :param creator: the creator of the environment

        :raises RuntimeError: when an image cannot be built, a wheel entry is invalid or a download fails

        """
        if not self.enabled:
            return
        with self._get_seed_wheels(creator) as name_to_whl:
            installer_class = self.installer_class(name_to_whl["pip"].version_tuple if "pip" in name_to_whl else None)
            exceptions = {}

            def _install(name: str, wheel: Wheel) -> None:
                LOGGER.debug("install %s from wheel %s via %s", name, wheel, installer_class.__name__)
                try:
                    key = Path(installer_class.__name__) / wheel.path.stem
                    wheel_img = self.app_data.wheel_image(creator.interpreter.version_release_str, key)
                    installer = installer_class(wheel.path, creator, wheel_img)
                    _build_wheel_image(self.app_data.lock / wheel_img.parent, wheel_img.name, installer)
                    # version_info is a VersionInfo, which install types as a plain tuple
                    installer.install(creator.interpreter.version_info)  # ty: ignore[invalid-argument-type]
                # the failure is stored and raised once every install has finished
                except Exception:  # ruff:ignore[blind-except]
                    exceptions[name] = sys.exc_info()

            threads = [Thread(target=_install, args=(n, w)) for n, w in name_to_whl.items()]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
            if exceptions:
                messages = [f"failed to build image {', '.join(exceptions.keys())} because:"]
                for value in exceptions.values():
                    exc_type, exc_value, exc_traceback = value
                    messages.append("".join(traceback.format_exception(exc_type, exc_value, exc_traceback)))
                raise RuntimeError("\n".join(messages))

    @contextmanager
    # the wheel lookup and its image build share one context, splitting it passes the lock around
    def _get_seed_wheels(self, creator: Creator) -> Generator[dict[str, Wheel], None, None]:  # ruff:ignore[complex-structure]
        name_to_whl, lock, fail = {}, Lock(), {}

        def _get(distribution: str, version: str | None) -> None:
            for_py_version = creator.interpreter.version_release_str
            failure, result = None, None
            # fallback to download in case the exact version is not available
            for download in [True] if self.download else [False, True]:
                failure = None
                try:
                    result = get_wheel(
                        distribution=distribution,
                        version=version,
                        for_py_version=for_py_version,
                        search_dirs=self.extra_search_dir,
                        download=download,
                        app_data=self.app_data,
                        do_periodic_update=self.periodic_update,
                        env=self.env,
                    )
                    if result is not None:
                        break
                except Exception as exception:
                    LOGGER.exception("fail")
                    failure = exception
            if failure:
                if isinstance(failure, CalledProcessError):
                    msg = f"failed to download {distribution}"
                    if version is not None:
                        msg += f" version {version}"
                    msg += f", pip download exit code {failure.returncode}"
                    if output := failure.output + failure.stderr:
                        msg += "\n"
                        msg += output
                else:
                    msg = repr(failure)
                LOGGER.error(msg)
                with lock:
                    fail[distribution] = version
            else:
                with lock:
                    name_to_whl[distribution] = result

        threads = [
            Thread(target=_get, args=(distribution, version))
            for distribution, version in self.distribution_to_versions().items()
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        if fail:
            msg = f"seed failed due to failing to download wheels {', '.join(fail.keys())}"
            raise RuntimeError(msg)
        yield name_to_whl

    def installer_class(self, pip_version_tuple: tuple[int, ...] | None) -> type[PipInstall]:
        """Return the installer class for the pip version, which symlinks the files when pip supports it.

        :param pip_version_tuple: the version of the seed pip, ``None`` when unknown

        :returns: the symlink installer when symlinks are requested and supported, otherwise the copy installer

        """
        if self.symlinks and pip_version_tuple and pip_version_tuple >= (19, 3):  # symlink support requires pip 19.3+
            return SymlinkPipInstall
        return CopyPipInstall


def _build_wheel_image(parent: PathLockBase, name: str, installer: PipInstall) -> None:
    with parent.non_reentrant_lock_for_key(name):
        if not installer.has_image():
            installer.build_image()


__all__ = [
    "FromAppData",
]
