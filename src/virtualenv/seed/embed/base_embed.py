from abc import ABCMeta
from pathlib import Path

from ..seeder import Seeder
from ..wheels import Version

PERIODIC_UPDATE_ON_BY_DEFAULT = True


class BaseEmbed(Seeder, metaclass=ABCMeta):
    def __init__(self, options):
        super().__init__(options, enabled=options.no_seed is False)

        self.download = options.download
        self.extra_search_dir = [i.resolve() for i in options.extra_search_dir if i.exists()]

        self.pip_version = options.pip
        self.setuptools_version = options.setuptools
        self.wheel_version = options.wheel

        self.no_pip = options.no_pip
        self.no_setuptools = options.no_setuptools
        self.no_wheel = options.no_wheel
        self.app_data = options.app_data
        self.periodic_update = not options.no_periodic_update

        if not self.distribution_to_versions():
            self.enabled = False

    @classmethod
    def distributions(cls):
        return {
            "pip": Version.bundle,
            "setuptools": Version.bundle,
            "wheel": Version.bundle,
        }

    def distribution_to_versions(self):
        return {
            distribution: getattr(self, f"{distribution}_version")
            for distribution in self.distributions()
            if getattr(self, f"no_{distribution}") is False
        }

    @classmethod
    def add_parser_arguments(cls, parser, interpreter, app_data):  # noqa: U100
        group = parser.add_mutually_exclusive_group()
        group.add_argument(
            "--no-download",
            "--never-download",
            dest="download",
            action="store_false",
            help=f"pass to disable download of the latest {'/'.join(cls.distributions())} from PyPI",
            default=True,
        )
        group.add_argument(
            "--download",
            dest="download",
            action="store_true",
            help=f"pass to enable download of the latest {'/'.join(cls.distributions())} from PyPI",
            default=False,
        )
        parser.add_argument(
            "--extra-search-dir",
            metavar="d",
            type=Path,
            nargs="+",
            help="a path containing wheels to extend the internal wheel list (can be set 1+ times)",
            default=[],
        )
        for distribution, default in cls.distributions().items():
            parser.add_argument(
                f"--{distribution}",
                dest=distribution,
                metavar="version",
                help=f"version of {distribution} to install as seed: embed, bundle or exact version",
                default=default,
            )
        for distribution in cls.distributions():
            parser.add_argument(
                f"--no-{distribution}",
                dest=f"no_{distribution}",
                action="store_true",
                help=f"do not install {distribution}",
                default=False,
            )
        parser.add_argument(
            "--no-periodic-update",
            dest="no_periodic_update",
            action="store_true",
            help="disable the periodic (once every 14 days) update of the embedded wheels",
            default=not PERIODIC_UPDATE_ON_BY_DEFAULT,
        )

    def __repr__(self):
        result = self.__class__.__name__
        result += "("
        if self.extra_search_dir:
            result += f"extra_search_dir={', '.join(str(i) for i in self.extra_search_dir)},"
        result += f"download={self.download},"
        for distribution in self.distributions():
            if getattr(self, f"no_{distribution}"):
                continue
            ver = f"={getattr(self, f'{distribution}_version', None) or 'latest'}"
            result += f" {distribution}{ver},"
        return result[:-1] + ")"


__all__ = [
    "BaseEmbed",
]
