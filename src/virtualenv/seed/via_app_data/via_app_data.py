"""Bootstrap"""
from __future__ import absolute_import, unicode_literals

import logging
import shutil
from contextlib import contextmanager
from threading import Lock, Thread

import six

from virtualenv.dirs import default_data_dir
from virtualenv.info import fs_supports_symlink
from virtualenv.seed.embed.base_embed import BaseEmbed
from virtualenv.seed.embed.wheels.acquire import get_wheels

from .pip_install.copy import CopyPipInstall
from .pip_install.symlink import SymlinkPipInstall


class FromAppData(BaseEmbed):
    def __init__(self, options):
        super(FromAppData, self).__init__(options)
        self.clear = options.clear_app_data
        self.app_data_dir = default_data_dir() / "seed-v1"
        self.symlinks = options.symlink_app_data

    @classmethod
    def add_parser_arguments(cls, parser, interpreter):
        super(FromAppData, cls).add_parser_arguments(parser, interpreter)
        parser.add_argument(
            "--clear-app-data",
            dest="clear_app_data",
            action="store_true",
            help="clear the app data folder of seed images ({})".format((default_data_dir() / "seed-v1").path),
            default=False,
        )
        can_symlink = fs_supports_symlink()
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
        base_cache = self.app_data_dir / creator.interpreter.version_release_str
        with self._get_seed_wheels(creator, base_cache) as name_to_whl:
            pip_version = name_to_whl["pip"].stem.split("-")[1]
            installer_class = self.installer_class(pip_version)

            def _install(name, wheel):
                logging.debug("install %s from wheel %s via %s", name, wheel, installer_class.__name__)
                image_folder = base_cache.path / "image" / installer_class.__name__ / wheel.stem
                installer = installer_class(wheel, creator, image_folder)
                if self.clear:
                    installer.clear()
                if not installer.has_image():
                    installer.build_image()
                installer.install()

            threads = list(Thread(target=_install, args=(n, w)) for n, w in name_to_whl.items())
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()

    @contextmanager
    def _get_seed_wheels(self, creator, base_cache):
        with base_cache.lock_for_key("wheels"):
            wheels_to = base_cache.path / "wheels"
            if self.clear and wheels_to.exists():
                shutil.rmtree(six.ensure_text(str(wheels_to)))
            wheels_to.mkdir(parents=True, exist_ok=True)
            name_to_whl, lock = {}, Lock()

            def _get(package, version):
                result = get_wheels(
                    creator.interpreter.version_release_str,
                    wheels_to,
                    self.extra_search_dir,
                    self.download,
                    {package: version},
                )
                with lock:
                    name_to_whl.update(result)

            threads = list(Thread(target=_get, args=(pkg, v)) for pkg, v in self.package_version().items())
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()

            yield name_to_whl

    def installer_class(self, pip_version):
        if self.symlinks:
            # symlink support requires pip 19.3+
            pip_version_int = tuple(int(i) for i in pip_version.split(".")[0:2])
            if pip_version_int >= (19, 3):
                return SymlinkPipInstall
        return CopyPipInstall

    def __unicode__(self):
        return super(FromAppData, self).__unicode__() + " app_data_dir={} via={}".format(
            self.app_data_dir.path, "symlink" if self.symlinks else "copy"
        )
