from __future__ import absolute_import, unicode_literals

from abc import ABCMeta

from six import add_metaclass

from virtualenv.util.path import Path
from virtualenv.util.six import ensure_str, ensure_text

from ..seeder import Seeder
from ..wheels import Version

PERIODIC_UPDATE_ON_BY_DEFAULT = True


def _parse_basic_req(line):
    parts = line.split("==")
    if len(parts) == 1:
        return (line, None)
    return (parts[0], parts[1])


@add_metaclass(ABCMeta)
class BaseEmbed(Seeder):
    def __init__(self, options):
        super(BaseEmbed, self).__init__(options, enabled=options.no_seed is False)

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
        self.seed_package = options.seed_package

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
        distributions = dict(self.seed_package)
        for distribution in self.distributions():
            if getattr(self, "no_{}".format(distribution)):
                distributions.pop(distribution, None)
            else:
                version = getattr(self, "{}_version".format(distribution))
                distributions[distribution] = version
        return distributions

    @classmethod
    def add_parser_arguments(cls, parser, interpreter, app_data):
        group = parser.add_mutually_exclusive_group()
        group.add_argument(
            "--no-download",
            "--never-download",
            dest="download",
            action="store_false",
            help="pass to disable download of the latest {} from PyPI".format("/".join(cls.distributions())),
            default=True,
        )
        group.add_argument(
            "--download",
            dest="download",
            action="store_true",
            help="pass to enable download of the latest {} from PyPI".format("/".join(cls.distributions())),
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
                "--{}".format(distribution),
                dest=distribution,
                metavar="version",
                help="version of {} to install as seed: embed, bundle or exact version".format(distribution),
                default=default,
            )
        for distribution in cls.distributions():
            parser.add_argument(
                "--no-{}".format(distribution),
                dest="no_{}".format(distribution),
                action="store_true",
                help="do not install {}".format(distribution),
                default=False,
            )
        parser.add_argument(
            "--no-periodic-update",
            dest="no_periodic_update",
            action="store_true",
            help="disable the periodic (once every 14 days) update of the embedded wheels",
            default=not PERIODIC_UPDATE_ON_BY_DEFAULT,
        )
        parser.add_argument(
            "--seed-package",
            metavar="package[==version]",
            dest="seed_package",
            nargs="+",
            type=_parse_basic_req,
            help="a list of extra packages to install",
            default=[],
        )

    def __unicode__(self):
        result = self.__class__.__name__
        result += "("
        if self.extra_search_dir:
            result += "extra_search_dir={},".format(", ".join(ensure_text(str(i)) for i in self.extra_search_dir))
        result += "download={},".format(self.download)
        for distribution in self.distributions():
            if getattr(self, "no_{}".format(distribution)):
                continue
            result += " {}{},".format(
                distribution,
                "={}".format(getattr(self, "{}_version".format(distribution), None) or "latest"),
            )
        return result[:-1] + ")"

    def __repr__(self):
        return ensure_str(self.__unicode__())
