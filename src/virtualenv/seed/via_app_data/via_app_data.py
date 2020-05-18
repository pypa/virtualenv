"""Bootstrap"""
from __future__ import absolute_import, unicode_literals

import logging
from contextlib import contextmanager
from functools import partial
from subprocess import CalledProcessError
from threading import Lock, Thread

import six

from virtualenv.info import fs_supports_symlink
from virtualenv.seed.embed.base_embed import BaseEmbed

from ..embed.wheels.acquire import get_wheel
from .pip_install.copy import CopyPipInstall
from .pip_install.symlink import SymlinkPipInstall


class FromAppData(BaseEmbed):
    def __init__(self, options):
        super(FromAppData, self).__init__(options)
        self.symlinks = options.symlink_app_data
        self.base_cache = self.app_data / "seed-app-data" / "v1.0.1"

    @classmethod
    def add_parser_arguments(cls, parser, interpreter, app_data):
        super(FromAppData, cls).add_parser_arguments(parser, interpreter, app_data)
        can_symlink = app_data.transient is False and fs_supports_symlink()
        parser.add_argument(
            "--symlink-app-data",
            dest="symlink_app_data",
            action="store_true" if can_symlink else "store_false",
            help="{} symlink the python packages from the app-data folder (requires seed pip>=19.3)".format(
                "" if can_symlink else "not supported - ",
            ),
            default=False,
        )

    def run(self, creator):
        if not self.enabled:
            return
        base_cache = self.base_cache / creator.interpreter.version_release_str
        with self._get_seed_wheels(creator, base_cache) as name_to_whl:
            pip_version = name_to_whl["pip"].version_tuple if "pip" in name_to_whl else None
            installer_class = self.installer_class(pip_version)

            def _install(name, wheel):
                logging.debug("install %s from wheel %s via %s", name, wheel, installer_class.__name__)
                image_folder = base_cache.path / "image" / installer_class.__name__ / wheel.path.stem
                installer = installer_class(wheel.path, creator, image_folder)
                if not installer.has_image():
                    installer.build_image()
                installer.install(creator.interpreter.version_info)

            threads = list(Thread(target=_install, args=(n, w)) for n, w in name_to_whl.items())
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()

    @contextmanager
    def _get_seed_wheels(self, creator, base_cache):
        with base_cache.lock_for_key("wheels"):
            wheels_to = base_cache.path / "wheels"
            wheels_to.mkdir(parents=True, exist_ok=True)
            name_to_whl, lock, fail = {}, Lock(), {}

            def _get(distribution, version):
                for_py_version = creator.interpreter.version_release_str
                loader = partial(get_wheel, distribution, version, for_py_version, self.extra_search_dir)
                failure, result = None, None
                # fallback to download in case the exact version is not available
                for download in [True] if self.download else [False, True]:
                    failure = None
                    try:
                        result = loader(download, wheels_to, self.app_data)
                        if result:
                            break
                    except Exception as exception:
                        failure = exception
                if failure:
                    if isinstance(failure, CalledProcessError):
                        msg = "failed to download {}".format(distribution)
                        if version is not None:
                            msg += " version {}".format(version)
                        msg += ", pip download exit code {}".format(failure.returncode)
                        output = failure.output if six.PY2 else (failure.output + failure.stderr)
                        if output:
                            msg += "\n"
                            msg += output
                    else:
                        msg = repr(failure)
                    logging.error(msg)
                    with lock:
                        fail[distribution] = version
                else:
                    with lock:
                        name_to_whl[distribution] = result

            threads = list(
                Thread(target=_get, args=(distribution, version))
                for distribution, version in self.distribution_to_versions().items()
            )
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
            if fail:
                raise RuntimeError("seed failed due to failing to download wheels {}".format(", ".join(fail.keys())))
            yield name_to_whl

    def installer_class(self, pip_version_tuple):
        if self.symlinks and pip_version_tuple:
            # symlink support requires pip 19.3+
            if pip_version_tuple >= (19, 3):
                return SymlinkPipInstall
        return CopyPipInstall

    def __unicode__(self):
        base = super(FromAppData, self).__unicode__()
        msg = ", via={}, app_data_dir={}".format("symlink" if self.symlinks else "copy", self.base_cache.path)
        return base[:-1] + msg + base[-1]
