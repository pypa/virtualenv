from __future__ import absolute_import, unicode_literals


def seed_package_args(options, parser):
    seed = parser.add_argument_group("bootstrap the environment with a package manager")
    seed.add_argument(
        "--without-pip",
        help="install pip as a package manager (plus setuptools)",
        action="store_true",
        dest="without_pip",
    )

    group = seed.add_mutually_exclusive_group()
    group.add_argument(
        "--download",
        dest="download",
        action="store_true",
        help="download latest pip/setuptools from PyPi",
        default=options.download,
    )
    group.add_argument(
        "--no-download",
        dest="download",
        action="store_false",
        help="do not download latest pip/setuptools from PyPi",
        default=not options.download,
    )

    for package in ["pip", "setuptools"]:
        seed.add_argument(
            "--{}".format(package),
            dest=package,
            metavar="version",
            help="{} version to install, default: latest from cache, bundle for bundled".format(package),
            default=getattr(options, package),
        )
