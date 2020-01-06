"""Bootstrap"""
from __future__ import absolute_import, unicode_literals

import logging
import shutil

import six

from virtualenv.info import IS_WIN, get_default_data_dir
from virtualenv.seed.embed.base_embed import BaseEmbed
from virtualenv.seed.embed.wheels.acquire import get_wheels

from .pip_install.copy import CopyPipInstall
from .pip_install.symlink import SymlinkPipInstall


class FromAppData(BaseEmbed):
    def __init__(self, options):
        super(FromAppData, self).__init__(options)
        self.clear = options.clear_app_data
        self.app_data_dir = get_default_data_dir() / "seed-v1"

    @classmethod
    def add_parser_arguments(cls, parser):
        super(FromAppData, cls).add_parser_arguments(parser)
        parser.add_argument(
            "--clear-app-data",
            dest="clear_app_data",
            action="store_true",
            help="clear the app data folder",
            default=False,
        )

    def run(self, creator):
        base_cache = self.app_data_dir / creator.interpreter.version_release_str
        name_to_whl = self._get_seed_wheels(creator, base_cache)
        installer_class = self.installer_class(name_to_whl["pip"].stem.split("-")[1])
        for name, wheel in name_to_whl.items():
            logging.debug("install %s from wheel %s", name, wheel)
            image_folder = base_cache / "image" / installer_class.__name__ / wheel.stem
            installer = installer_class(wheel, creator, image_folder)
            if self.clear:
                installer.clear()
            if not installer:
                installer.build_image()
            installer.install()

    def _get_seed_wheels(self, creator, base_cache):
        wheels_to = base_cache / "wheels"
        if self.clear and wheels_to.exists():
            shutil.rmtree(six.ensure_text(str(wheels_to)))
        wheels_to.mkdir(parents=True, exist_ok=True)
        name_to_whl = get_wheels(
            creator.interpreter.version_release_str,
            wheels_to,
            self.extra_search_dir,
            self.download,
            self.pip_version,
            self.setuptools_version,
        )
        return name_to_whl

    @staticmethod
    def installer_class(pip_version):
        # on Windows symlinks are unreliable, but we have junctions for folders
        if not IS_WIN:
            # symlink support requires pip 19.3+
            pip_version_int = tuple(int(i) for i in pip_version.split(".")[0:2])
            if pip_version_int >= (19, 3):
                return SymlinkPipInstall
        return CopyPipInstall
