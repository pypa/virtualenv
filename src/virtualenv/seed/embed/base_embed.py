from __future__ import absolute_import, unicode_literals

from abc import ABCMeta

import six

from ..seeder import Seeder


@six.add_metaclass(ABCMeta)
class BaseEmbed(Seeder):
    def __init__(self, options):
        super(Seeder, self).__init__()
        self.enabled = options.without_pip is False
        self.download = options.download
        self.pip_version = options.pip
        self.setuptools_version = options.setuptools

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

        for package in ["pip", "setuptools"]:
            parser.add_argument(
                "--{}".format(package),
                dest=package,
                metavar="version",
                help="{} version to install, default: latest from cache, bundle for bundled".format(package),
                default=None,
            )
