"""Bootstrap"""
from __future__ import absolute_import, unicode_literals

import logging
from contextlib import contextmanager
from functools import partial
from threading import Lock, Thread

from virtualenv.info import fs_supports_symlink
from virtualenv.seed.embed.base_embed import BaseEmbed
from virtualenv.seed.embed.wheels.acquire import WheelDownloadFail, get_wheels
from virtualenv.util.path import safe_delete

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
                "" if can_symlink else "not supported - "
            ),
            default=False,
        )

    def run(self, creator):
        if not self.enabled:
            return
        base_cache = self.base_cache / creator.interpreter.version_release_str
        with self._get_seed_wheels(creator, base_cache) as name_to_whl:
            pip_version = name_to_whl["pip"].stem.split("-")[1] if "pip" in name_to_whl else None
            installer_class = self.installer_class(pip_version)

            def _install(name, wheel):
                logging.debug("install %s from wheel %s via %s", name, wheel, installer_class.__name__)
                image_folder = base_cache.path / "image" / installer_class.__name__ / wheel.stem
                installer = installer_class(wheel, creator, image_folder)
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
            if wheels_to.exists():
                safe_delete(wheels_to)
            wheels_to.mkdir(parents=True, exist_ok=True)
            name_to_whl, lock, fail = {}, Lock(), {}

            def _get(package, version):
                wheel_loader = partial(
                    get_wheels,
                    creator.interpreter.version_release_str,
                    wheels_to,
                    self.extra_search_dir,
                    {package: version},
                    self.app_data,
                )
                failure, result = None, None
                # fallback to download in case the exact version is not available
                for download in [True] if self.download else [False, True]:
                    failure = None
                    try:
                        result = wheel_loader(download)
                        if result:
                            break
                    except Exception as exception:
                        failure = exception
                if failure:
                    if isinstance(failure, WheelDownloadFail):
                        msg = "failed to download {}".format(package)
                        if version is not None:
                            msg += " version {}".format(version)
                        msg += ", pip download exit code {}".format(failure.exit_code)
                        output = failure.out + failure.err
                        if output:
                            msg += "\n"
                            msg += output
                    else:
                        msg = repr(failure)
                    logging.error(msg)
                    with lock:
                        fail[package] = version
                else:
                    with lock:
                        name_to_whl.update(result)

            package_versions = self.package_version()
            threads = list(Thread(target=_get, args=(pkg, v)) for pkg, v in package_versions.items())
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
            if fail:
                raise RuntimeError("seed failed due to failing to download wheels {}".format(", ".join(fail.keys())))
            yield name_to_whl

    def installer_class(self, pip_version):
        if self.symlinks and pip_version:
            # symlink support requires pip 19.3+
            pip_version_int = tuple(int(i) for i in pip_version.split(".")[0:2])
            if pip_version_int >= (19, 3):
                return SymlinkPipInstall
        return CopyPipInstall

    def __unicode__(self):
        base = super(FromAppData, self).__unicode__()
        msg = ", via={}, app_data_dir={}".format("symlink" if self.symlinks else "copy", self.base_cache.path)
        return base[:-1] + msg + base[-1]
