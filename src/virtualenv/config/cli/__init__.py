from __future__ import absolute_import, unicode_literals

import re

from ..options import BaseOption
from .parser import make_base_parser, make_core_parser


def parse_base_cli(args):
    options = BaseOption()
    parse = make_base_parser(options)

    result_ns, _ = parse.parse_known_args(args)
    for key in vars(result_ns):
        setattr(options, key, getattr(result_ns, key))

    return options


def parse_core_cli(args, creator_class, interpreter):
    options = creator_class.default_options(interpreter)
    parse = make_core_parser(options)
    creator_class.extend_parser(parse, options, interpreter)
    result_ns = parse.parse_args(args=args)
    for key in vars(result_ns):
        setattr(options, key, getattr(result_ns, key))
    return options


def _fix_seed_packages(seed_packages, result_ns):
    """act on the no pip/wheel/setuptools"""
    to_install = []
    for pkg in seed_packages:
        if pkg:
            if result_ns.no_setuptools or result_ns.no_pip or result_ns.no_wheel:
                match = re.match(r"([a-zA-Z0-9][a-zA-Z0-9-_.]*).*", pkg)
                if match:
                    raw_pkg = match.group(0)
                    if (
                        (result_ns.no_pip and raw_pkg == "pip")
                        or (result_ns.no_setuptools and raw_pkg == "setuptools")
                        or (result_ns.no_wheel and raw_pkg == "wheel")
                    ):
                        continue
            to_install.append(pkg)
    return to_install
