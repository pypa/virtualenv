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


def run_via_cli(args):
    """Run the virtual environment creation via CLI arguments

    :param args: the command line arguments
    :return: the creator used
    """
    session = session_via_cli(args)
    session.run()
    return session


def session_via_cli(args):
    parser = VirtualEnvConfigParser()
    add_version_flag(parser)
    options, verbosity = _do_report_setup(parser, args)
    discover = get_discover(parser, args, options)
    interpreter = discover.interpreter
    if interpreter is None:
        raise RuntimeError("failed to find interpreter for {}".format(discover))
    elements = [
        CreatorSelector(interpreter, parser),
        SeederSelector(interpreter, parser),
        ActivationSelector(interpreter, parser),
    ]
    parser.parse_known_args(args, namespace=options)
    for element in elements:
        element.handle_selected_arg_parse(options)
    parser.enable_help()
    parser.parse_args(args, namespace=options)
    creator, seeder, activators = tuple(e.create(options) for e in elements)  # create types
    session = Session(verbosity, interpreter, creator, seeder, activators)
    return session


def add_version_flag(parser):
    import virtualenv

    parser.add_argument(
        "--version", action="version", version="%(prog)s {} from {}".format(__version__, virtualenv.__file__)
    )


def _do_report_setup(parser, args):
    level_map = ", ".join("{}:{}".format(c, logging.getLevelName(l)) for c, l in sorted(list(LEVELS.items())))
    msg = "verbosity = verbose - quiet, default {}, count mapping = {{{}}}"
    verbosity_group = parser.add_argument_group(msg.format(logging.getLevelName(LEVELS[3]), level_map))
    verbosity = verbosity_group.add_mutually_exclusive_group()
    verbosity.add_argument("-v", "--verbose", action="count", dest="verbose", help="increase verbosity", default=2)
    verbosity.add_argument("-q", "--quiet", action="count", dest="quiet", help="decrease verbosity", default=0)
    options, _ = parser.parse_known_args(args)
    verbosity_value = setup_report(options.verbose, options.quiet)
    return options, verbosity_value
