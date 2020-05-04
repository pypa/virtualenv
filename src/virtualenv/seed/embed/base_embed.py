from __future__ import absolute_import, unicode_literals

from abc import ABCMeta

from six import add_metaclass

from virtualenv.util.path import Path
from virtualenv.util.six import ensure_str, ensure_text

from ..seeder import Seeder


@add_metaclass(ABCMeta)
class BaseEmbed(Seeder):
    packages = ["pip", "setuptools", "wheel"]

    def __init__(self, options):
        super(BaseEmbed, self).__init__(options, enabled=options.no_seed is False)
        self.download = options.download
        self.extra_search_dir = [i.resolve() for i in options.extra_search_dir if i.exists()]

        def latest_is_none(key):
            value = getattr(options, key)
            return None if value == "latest" else value

        self.pip_version = latest_is_none("pip")
        self.setuptools_version = latest_is_none("setuptools")
        self.wheel_version = latest_is_none("wheel")

        self.no_pip = options.no_pip
        self.no_setuptools = options.no_setuptools
        self.no_wheel = options.no_wheel
        self.app_data = options.app_data.folder

        if not self.package_version():
            self.enabled = False

    def package_version(self):
        return {
            package: getattr(self, "{}_version".format(package))
            for package in self.packages
            if getattr(self, "no_{}".format(package)) is False
        }

    @classmethod
    def add_parser_arguments(cls, parser, interpreter, app_data):
        group = parser.add_mutually_exclusive_group()
        group.add_argument(
            "--no-download",
            "--never-download",
            dest="download",
            action="store_false",
            help="pass to disable download of the latest {} from PyPI".format("/".join(cls.packages)),
            default=True,
        )
        group.add_argument(
            "--download",
            dest="download",
            action="store_true",
            help="pass to enable download of the latest {} from PyPI".format("/".join(cls.packages)),
            default=False,
        )
        parser.add_argument(
            "--extra-search-dir",
            metavar="d",
            type=Path,
            nargs="+",
            help="a path containing wheels the seeder may also use beside bundled (can be set 1+ times)",
            default=[],
        )
        for package in cls.packages:
            parser.add_argument(
                "--{}".format(package),
                dest=package,
                metavar="version",
                help="{} version to install, bundle for bundled".format(package),
                default="latest",
            )
        for package in cls.packages:
            parser.add_argument(
                "--no-{}".format(package),
                dest="no_{}".format(package),
                action="store_true",
                help="do not install {}".format(package),
                default=False,
            )

    def __unicode__(self):
        result = self.__class__.__name__
        result += "("
        if self.extra_search_dir:
            result += "extra_search_dir={},".format(", ".join(ensure_text(str(i)) for i in self.extra_search_dir))
        result += "download={},".format(self.download)
        for package in self.packages:
            if getattr(self, "no_{}".format(package)):
                continue
            result += " {}{},".format(
                package, "={}".format(getattr(self, "{}_version".format(package), None) or "latest")
            )
        return result[:-1] + ")"

    def __repr__(self):
        return ensure_str(self.__unicode__())
