from __future__ import absolute_import, unicode_literals

import logging

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
    :param options: passing in a ``argparse.Namespace`` object allows return of the parsed options
    :return: the session object of the creation (its structure for now is experimental and might change on short notice)
    """
    session = session_via_cli(args, options)
    session.run()
    return session


# noinspection PyProtectedMember
def session_via_cli(args, options=None):
    parser = build_parser(args, options)
    parser.parse_args(args, namespace=parser._options)
    creator, seeder, activators = tuple(e.create(parser._options) for e in parser._elements)  # create types
    session = Session(parser._verbosity, parser._interpreter, creator, seeder, activators)
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
    parser._options, parser._verbosity = _do_report_setup(parser, args)
    discover = get_discover(parser, args, parser._options)
    parser._interpreter = interpreter = discover.interpreter
    if interpreter is None:
        raise RuntimeError("failed to find interpreter for {}".format(discover))
    parser._elements = [
        CreatorSelector(interpreter, parser),
        SeederSelector(interpreter, parser),
        ActivationSelector(interpreter, parser),
    ]
    parser.parse_known_args(args, namespace=parser._options)
    for element in parser._elements:
        element.handle_selected_arg_parse(parser._options)
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
    options, _ = parser.parse_known_args(args, namespace=parser._options)
    verbosity_value = setup_report(options.verbose, options.quiet)
    return options, verbosity_value
