from __future__ import absolute_import, unicode_literals

import logging
from argparse import ArgumentTypeError

from entrypoints import get_group_named

from .config.cli.parser import VirtualEnvConfigParser
from .report import LEVELS, setup_report
from .session import Session


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
    options, verbosity = _do_report_setup(parser, args)
    discover = _get_discover(parser, args, options)
    interpreter = discover.interpreter
    logging.debug("target interpreter %r", interpreter)
    if interpreter is None:
        raise RuntimeError("failed to find interpreter for {}".format(discover))
    elements = [
        _get_creator(interpreter, parser, options),
        _get_seeder(parser, options),
        _get_activation(interpreter, parser, options),
    ]
    [next(elem) for elem in elements]  # add choice of types
    parser.parse_known_args(args, namespace=options)
    [next(elem) for elem in elements]  # add type flags
    parser.enable_help()
    parser.parse_args(args, namespace=options)
    creator, seeder, activators = tuple(next(e) for e in elements)  # create types
    session = Session(verbosity, interpreter, creator, seeder, activators)
    return session


def _do_report_setup(parser, args):
    level_map = ", ".join("{}:{}".format(c, logging.getLevelName(l)) for c, l in sorted(list(LEVELS.items())))
    msg = "verbosity = verbose - quiet, default {}, count mapping = {{{}}}"
    verbosity_group = parser.add_argument_group(msg.format(logging.getLevelName(LEVELS[3]), level_map))
    verbosity = verbosity_group.add_mutually_exclusive_group()
    verbosity.add_argument("-v", "--verbose", action="count", dest="verbose", help="increase verbosity", default=3)
    verbosity.add_argument("-q", "--quiet", action="count", dest="quiet", help="decrease verbosity", default=0)
    options, _ = parser.parse_known_args(args)
    verbosity_value = setup_report(options.verbose, options.quiet)
    return options, verbosity_value


def _get_discover(parser, args, options):
    discover_types = _collect_discovery_types()
    discovery_parser = parser.add_argument_group("target interpreter identifier")
    discovery_parser.add_argument(
        "--discovery",
        choices=list(discover_types.keys()),
        default=next(i for i in discover_types.keys()),
        required=False,
        help="interpreter discovery method",
    )
    options, _ = parser.parse_known_args(args, namespace=options)
    discover_class = discover_types[options.discovery]
    discover_class.add_parser_arguments(discovery_parser)
    options, _ = parser.parse_known_args(args, namespace=options)
    discover = discover_class(options)
    return discover


def _collect_discovery_types():
    discover_types = {e.name: e.load() for e in get_group_named("virtualenv.discovery").values()}
    return discover_types


def _get_creator(interpreter, parser, options):
    creators = _collect_creators(interpreter)
    creator_parser = parser.add_argument_group("creator options")
    creator_parser.add_argument(
        "--creator",
        choices=list(creators),
        # prefer the built-in venv if present, otherwise fallback to first defined type
        default="venv" if "venv" in creators else next(iter(creators), None),
        required=False,
        help="create environment via",
    )
    yield
    if options.creator not in creators:
        raise RuntimeError("No virtualenv implementation for {}".format(interpreter))
    creator_class = creators[options.creator]
    creator_class.add_parser_arguments(creator_parser, interpreter)
    yield
    creator = creator_class(options, interpreter)
    yield creator


def _collect_creators(interpreter):
    all_creators = {e.name: e.load() for e in get_group_named("virtualenv.create").values()}
    creators = {k: v for k, v in all_creators.items() if v.supports(interpreter)}
    return creators


def _get_seeder(parser, options):
    seed_parser = parser.add_argument_group("package seeder")
    seeder_types = _collect_seeders()
    seed_parser.add_argument(
        "--seeder",
        choices=list(seeder_types.keys()),
        default="link-app-data",
        required=False,
        help="seed packages install method",
    )
    seed_parser.add_argument(
        "--without-pip",
        help="if set forces the none seeder, used for compatibility with venv",
        action="store_true",
        dest="without_pip",
    )
    yield
    seeder_class = seeder_types["none" if options.without_pip is True else options.seeder]
    seeder_class.add_parser_arguments(seed_parser)
    yield
    seeder = seeder_class(options)
    yield seeder


def _collect_seeders():
    seeder_types = {e.name: e.load() for e in get_group_named("virtualenv.seed").values()}
    return seeder_types


def _get_activation(interpreter, parser, options):
    activator_parser = parser.add_argument_group("activation script generator")
    compatible = collect_activators(interpreter)
    default = ",".join(compatible.keys())

    def _extract_activators(entered_str):
        elements = [e.strip() for e in entered_str.split(",") if e.strip()]
        missing = [e for e in elements if e not in compatible]
        if missing:
            raise ArgumentTypeError("the following activators are not available {}".format(",".join(missing)))
        return elements

    activator_parser.add_argument(
        "--activators",
        default=default,
        metavar="comma_separated_list",
        required=False,
        help="activators to generate together with virtual environment - default is all available and compatible",
        type=_extract_activators,
    )
    yield

    selected_activators = _extract_activators(default) if options.activators is default else options.activators
    active_activators = {k: v for k, v in compatible.items() if k in selected_activators}
    activator_parser.add_argument(
        "--prompt",
        dest="prompt",
        metavar="prompt",
        help="provides an alternative prompt prefix for this environment",
        default=None,
    )
    for activator in active_activators.values():
        activator.add_parser_arguments(parser)
    yield

    activator_instances = [activator_class(options) for activator_class in active_activators.values()]
    yield activator_instances


def collect_activators(interpreter):
    all_activators = {e.name: e.load() for e in get_group_named("virtualenv.activate").values()}
    activators = {k: v for k, v in all_activators.items() if v.supports(interpreter)}
    return activators
