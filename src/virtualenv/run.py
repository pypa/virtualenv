from __future__ import absolute_import, unicode_literals

import logging
import sys
from argparse import ArgumentTypeError
from collections import OrderedDict

from .config.cli.parser import VirtualEnvConfigParser
from .report import LEVELS, setup_report
from .session import Session
from .version import __version__

if sys.version_info >= (3, 8):
    from importlib.metadata import entry_points
else:
    from importlib_metadata import entry_points


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
    discover = _get_discover(parser, args, options)
    interpreter = discover.interpreter
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


_DISCOVERY = None
_ENTRY_POINTS = None


def plugins(key):
    global _ENTRY_POINTS
    if _ENTRY_POINTS is None:
        _ENTRY_POINTS = entry_points()
    return _ENTRY_POINTS[key]


def _collect_discovery_types():
    global _DISCOVERY
    if _DISCOVERY is None:
        _DISCOVERY = {e.name: e.load() for e in plugins("virtualenv.discovery")}
    return _DISCOVERY


def _get_creator(interpreter, parser, options):
    creators = _collect_creators(interpreter)
    creator_parser = parser.add_argument_group("creator options")
    choices = list(creators)
    from virtualenv.interpreters.create.self_do import SelfDo

    if "self-do" in creators:
        del creators["self-do"]
    self_do = next((i for i, v in creators.items() if issubclass(v, SelfDo)), None)
    if self_do is not None:
        choices.append("self-do")
    creator_parser.add_argument(
        "--creator",
        choices=choices,
        # prefer the built-in venv if present, otherwise fallback to first defined type
        default="venv" if "venv" in creators else next(iter(creators), None),
        required=False,
        help="create environment via{}".format("" if self_do is None else " (self-do = {})".format(self_do)),
    )
    yield
    selected = self_do if options.creator == "self-do" else options.creator
    if selected not in creators:
        raise RuntimeError("No virtualenv implementation for {}".format(interpreter))
    creator_class = creators[selected]
    creator_class.add_parser_arguments(creator_parser, interpreter)
    yield
    if selected == "venv":
        options.self_do = None if self_do is None else creators[self_do](options, interpreter)
    creator = creator_class(options, interpreter)
    yield creator


_CREATORS = None


def _collect_creators(interpreter):
    global _CREATORS
    if _CREATORS is None:
        _CREATORS = {e.name: e.load() for e in plugins("virtualenv.create")}
    creators = OrderedDict()
    for name, class_type in _CREATORS.items():
        if class_type.supports(interpreter):
            creators[name] = class_type
    return creators


def _get_seeder(parser, options):
    seed_parser = parser.add_argument_group("package seeder")
    seeder_types = _collect_seeders()
    seed_parser.add_argument(
        "--seeder",
        choices=list(seeder_types.keys()),
        default="app-data",
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


_SEEDERS = None


def _collect_seeders():
    global _SEEDERS
    if _SEEDERS is None:
        _SEEDERS = {e.name: e.load() for e in plugins("virtualenv.seed")}
    return _SEEDERS


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


_ACTIVATORS = None


def collect_activators(interpreter):
    global _ACTIVATORS
    if _ACTIVATORS is None:
        _ACTIVATORS = {e.name: e.load() for e in plugins("virtualenv.activate")}
    activators = {k: v for k, v in _ACTIVATORS.items() if v.supports(interpreter)}
    return activators
