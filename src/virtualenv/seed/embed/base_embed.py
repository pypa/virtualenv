from __future__ import absolute_import, unicode_literals

from abc import ABCMeta

import six

from virtualenv.util.path import Path

from ..seeder import Seeder


@six.add_metaclass(ABCMeta)
class BaseEmbed(Seeder):
    def __init__(self, options):
        super(Seeder, self).__init__()
        self.enabled = options.without_pip is False
        self.download = options.download
        self.extra_search_dir = [i.resolve() for i in options.extra_search_dir if i.exists()]
        self.pip_version = None if options.pip == "latest" else options.pip
        self.setuptools_version = None if options.setuptools == "latest" else options.setuptools
        self.no_pip = options.no_pip
        self.no_setuptools = options.no_setuptools

    @classmethod
    def add_parser_arguments(cls, parser):
        group = parser.add_mutually_exclusive_group()
        group.add_argument(
            "--download",
            dest="download",
            action="store_true",
            help="download latest pip/setuptools from PyPi",
            default=False,
        )
        group.add_argument(
            "--no-download",
            "--never-download",
            dest="download",
            action="store_false",
            help="do not download latest pip/setuptools from PyPi",
            default=True,
        )
        parser.add_argument(
            "--extra-search-dir",
            metavar="d",
            type=Path,
            nargs="+",
            help="a location containing wheels candidates to install from",
            default=[],
        )
        for package in ["pip", "setuptools"]:
            parser.add_argument(
                "--{}".format(package),
                dest=package,
                metavar="version",
                help="{} version to install, bundle for bundled".format(package),
                default="latest",
            )
        for extra, package in [
            ("", "pip"),
            ("", "setuptools"),
            ("N/A - kept only for backwards compatibility; ", "wheel"),
        ]:
            parser.add_argument(
                "--no-{}".format(package),
                dest="no_{}".format(package),
                action="store_true",
                help="{}do not install {}".format(extra, package),
                default=False,
            )

    def __str__(self):
        result = self.__class__.__name__
        if self.extra_search_dir:
            result += " extra search dirs = {}".format(
                ", ".join(six.ensure_text(str(i)) for i in self.extra_search_dir)
            )
        if self.no_pip is False:
            result += " pip{}".format("={}".format(self.pip_version or "latest"))
        if self.no_setuptools is False:
            result += " setuptools{}".format("={}".format(self.setuptools_version or "latest"))
        return result
