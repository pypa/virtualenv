from __future__ import annotations

import sys
from typing import TYPE_CHECKING, Final

from .base import PluginLoader

if TYPE_CHECKING:
    from virtualenv.config.cli.parser import VirtualEnvConfigParser
    from virtualenv.discovery.discover import Discover


class Discovery(PluginLoader):
    """Discovery plugins."""


def get_discover(parser: VirtualEnvConfigParser, args: list[str] | None) -> Discover:
    discover_types = Discovery.entry_points_for("virtualenv.discovery")
    discovery_parser = parser.add_argument_group(
        title="discovery",
        description="discover and provide a target interpreter",
    )
    choices = _get_default_discovery(discover_types)
    # prefer the builtin if present, otherwise fallback to first defined type
    choices = sorted(choices, key=lambda a: 0 if a == "builtin" else 1)
    try:
        default_discovery = next(iter(choices))
    except StopIteration as e:
        msg = "No discovery plugin found. Try reinstalling virtualenv to fix this issue."
        raise RuntimeError(msg) from e
    discovery_parser.add_argument(
        "--discovery",
        choices=choices,
        default=default_discovery,
        required=False,
        help="interpreter discovery method",
    )
    options, _ = parser.parse_known_args(args)
    discovery = options.discovery
    if discovery not in discover_types:
        available = ", ".join(sorted(discover_types))
        msg = (
            f"discovery {discovery!r} is not available. "
            f"Available discovery methods: {available}. "
            f"Is the plugin installed?"
        )
        raise RuntimeError(msg)
    discover_class = discover_types[discovery]
    discover_class.add_parser_arguments(discovery_parser)  # ty: ignore[unresolved-attribute]
    options, remaining = parser.parse_known_args(args, namespace=options)
    discovery_options: Final = {
        option
        # argparse has no public accessor for the arguments registered by a plugin.
        for action in discovery_parser._group_actions  # ruff: ignore[private-member-access]
        for option in action.option_strings
    }
    unregistered: Final = {value for value in remaining if value.startswith("-")}
    preceding = None
    for value in sys.argv[1:] if args is None else args:
        if value == "--":
            break
        if preceding is not None and (
            value.split("=", 1)[0] in discovery_options
            or any(value.startswith(option) for option in discovery_options if not option.startswith("--"))
        ):
            parser.error(f"discovery option {value!r} must precede unregistered option {preceding!r}")
        if value in unregistered:
            preceding = value
    return discover_class(options)


def _get_default_discovery(discover_types: dict[str, type]) -> list[str]:
    return list(discover_types.keys())


__all__ = [
    "Discovery",
    "get_discover",
]
