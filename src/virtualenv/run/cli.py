from __future__ import annotations

import os
from typing import TYPE_CHECKING

from .parser import build_parser
from .session import Session

if TYPE_CHECKING:
    from collections.abc import MutableMapping

    from virtualenv.config.cli.parser import VirtualEnvOptions


def cli_run(
    args: list[str],
    options: VirtualEnvOptions | None = None,
    # setup_logging keeps its default for existing callers
    setup_logging: bool = True,  # ruff:ignore[boolean-default-value-positional-argument]
    env: MutableMapping[str, str] | None = None,
) -> Session:
    """Create a virtual environment given some command line interface arguments.

    :param args: the command line arguments
    :param options: passing in a ``VirtualEnvOptions`` object allows return of the parsed options
    :param setup_logging: ``True`` if setup logging handlers, ``False`` to use handlers already registered
    :param env: environment variables to use

    :returns: the session object of the creation (its structure for now is experimental and might change on short
        notice)

    """
    env = os.environ if env is None else env
    of_session = session_via_cli(args, options, setup_logging, env)
    with of_session:
        of_session.run()
    return of_session


def session_via_cli(
    args: list[str],
    options: VirtualEnvOptions | None = None,
    # setup_logging keeps its default for existing callers
    setup_logging: bool = True,  # ruff:ignore[boolean-default-value-positional-argument]
    env: MutableMapping[str, str] | None = None,
) -> Session:
    """Create a virtualenv session (same as cli_run, but this does not perform the creation). Use this if you just want to query what the virtual environment would look like, but not actually create it.

    :param args: the command line arguments
    :param options: passing in a ``VirtualEnvOptions`` object allows return of the parsed options
    :param setup_logging: ``True`` if setup logging handlers, ``False`` to use handlers already registered
    :param env: environment variables to use

    :returns: the session object of the creation (its structure for now is experimental and might change on short
        notice)

    """
    env = os.environ if env is None else env
    parser, elements = build_parser(args, options, setup_logging, env)
    # parse_args returns a plain Namespace, not the VirtualEnvOptions it is typed as
    options = parser.parse_args(args)  # ty: ignore[invalid-assignment]
    # the parser carries the discovered interpreter to the session, which ty cannot see
    options.py_version = parser._interpreter.version_info  # ruff:ignore[private-member-access]  # ty: ignore[invalid-assignment, unresolved-attribute]
    creator, seeder, activators = tuple(
        # options is set by parse_args above, ty still sees the optional type
        e.create(options)  # ty: ignore[invalid-argument-type]
        for e in elements
    )  # create types
    return Session(
        # options is set by parse_args above, ty still sees the optional type
        options.verbosity,  # ty: ignore[unresolved-attribute, invalid-argument-type]
        # options is set by parse_args above, ty still sees the optional type
        options.app_data,  # ty: ignore[unresolved-attribute]
        # the parser carries the discovered interpreter to the session, which ty cannot see
        parser._interpreter,  # ruff:ignore[private-member-access]  # ty: ignore[invalid-argument-type]
        # the builders are untyped, so their create results are object to ty
        creator,  # ty: ignore[invalid-argument-type]
        # the builders are untyped, so their create results are object to ty
        seeder,  # ty: ignore[invalid-argument-type]
        # the builders are untyped, so their create results are object to ty
        activators,  # ty: ignore[invalid-argument-type]
    )


__all__ = [
    "cli_run",
    "session_via_cli",
]
