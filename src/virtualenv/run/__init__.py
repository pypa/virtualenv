from __future__ import absolute_import, unicode_literals

import logging

from virtualenv.run.app_data import AppDataAction

from ..config.cli.parser import VirtualEnvConfigParser
from ..report import LEVELS, setup_report
from ..session import Session
from ..version import __version__
from .plugin.activators import ActivationSelector
from .plugin.creators import CreatorSelector
from .plugin.discovery import get_discover
from .plugin.seeders import SeederSelector


def cli_run(args, options=None):
    """Create a virtual environment given some command line interface arguments

    :param args: the command line arguments
    :param options: passing in a ``VirtualEnvOptions`` object allows return of the parsed options
    :return: the session object of the creation (its structure for now is experimental and might change on short notice)
    """
    session = session_via_cli(args, options)
    with session:
        session.run()
    return session


# noinspection PyProtectedMember
def session_via_cli(args, options=None):
    parser = build_parser(args, options)
    options = parser.parse_args(args)
    creator, seeder, activators = tuple(e.create(options) for e in parser._elements)  # create types
    session = Session(options.verbosity, options.app_data, parser._interpreter, creator, seeder, activators)
    return session


# noinspection PyProtectedMember
def build_parser(args=None, options=None):
    parser = VirtualEnvConfigParser(options)
    add_version_flag(parser)
    parser.add_argument(
        "--with-traceback",
        dest="with_traceback",
        action="store_true",
        default=False,
        help="on failure also display the stacktrace internals of virtualenv",
    )
    _do_report_setup(parser, args)
    # here we need a write-able application data (e.g. the zipapp might need this for discovery cache)
    default_app_data = AppDataAction.default()
    parser.add_argument(
        "--app-data",
        dest="app_data",
        action=AppDataAction,
        default="<temp folder>" if default_app_data is None else default_app_data,
        help="a data folder used as cache by the virtualenv",
    )
    parser.add_argument(
        "--clear-app-data",
        dest="clear_app_data",
        action="store_true",
        help="start with empty app data folder",
        default=False,
    )
    discover = get_discover(parser, args)
    parser._interpreter = interpreter = discover.interpreter
    if interpreter is None:
        raise RuntimeError("failed to find interpreter for {}".format(discover))
    parser._elements = [
        CreatorSelector(interpreter, parser),
        SeederSelector(interpreter, parser),
        ActivationSelector(interpreter, parser),
    ]
    options, _ = parser.parse_known_args(args)
    for element in parser._elements:
        element.handle_selected_arg_parse(options)
    parser.enable_help()
    return parser


def add_version_flag(parser):
    import virtualenv

    parser.add_argument(
        "--version",
        action="version",
        version="%(prog)s {} from {}".format(__version__, virtualenv.__file__),
        help="display the version of the virtualenv package and it's location, then exit",
    )


def _do_report_setup(parser, args):
    level_map = ", ".join("{}={}".format(logging.getLevelName(l), c) for c, l in sorted(list(LEVELS.items())))
    msg = "verbosity = verbose - quiet, default {}, mapping => {}"
    verbosity_group = parser.add_argument_group(
        title="verbosity", description=msg.format(logging.getLevelName(LEVELS[3]), level_map)
    )
    verbosity = verbosity_group.add_mutually_exclusive_group()
    verbosity.add_argument("-v", "--verbose", action="count", dest="verbose", help="increase verbosity", default=2)
    verbosity.add_argument("-q", "--quiet", action="count", dest="quiet", help="decrease verbosity", default=0)
    option, _ = parser.parse_known_args(args)
    setup_report(option.verbosity)
