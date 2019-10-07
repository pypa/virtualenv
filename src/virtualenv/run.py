from __future__ import absolute_import, unicode_literals

import json
import logging

from .config import parse_base_cli, parse_core_cli
from .interpreters import get_creator_with_interpreter
from .report import setup_report


def run_via_cli(args):
    """Run the virtual environment creation via CLI arguments

    :param args: the command line arguments
    :return: the creator used
    """
    return _run_via_cli(args)


def _run_via_cli(args):
    base_opts = _parse_base_opts(args)
    creator_class, interpreter = _get_creator(base_opts)
    options = _parse_core_opts(args, base_opts, creator_class, interpreter)
    creator = creator_class(options, interpreter)
    _run_create(creator)
    logging.debug(_DEBUG_MARKER)
    logging.debug("%s", Debug(creator))
    return creator


def _run_create(creator):
    creator.run()


def _parse_base_opts(args):
    base_opts = parse_base_cli(args=args)
    setup_report(base_opts.verbosity)
    logging.debug(args)
    return base_opts


def _parse_core_opts(args, base_opts, creator_class, interpreter):
    options = parse_core_cli(args, creator_class, interpreter)
    if options.verbosity != base_opts.verbosity:
        setup_report(options.verbosity)  # pragma: no cover
    logging.debug("options %r", options)
    return options


def _get_creator(base_opts):
    creator_class, interpreter = get_creator_with_interpreter(base_opts.python)
    logging.debug("target interpreter %r", interpreter)
    logging.debug("creator %r", creator_class)
    return creator_class, interpreter


_DEBUG_MARKER = "=" * 30 + " target debug " + "=" * 30


class Debug(object):
    """lazily populate debug"""

    def __init__(self, creator):
        self.creator = creator

    def __str__(self):
        return json.dumps(self.creator.debug, indent=2)
