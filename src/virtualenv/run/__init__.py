from __future__ import annotations

from virtualenv.app_data import make_app_data as make_app_data
from virtualenv.config.cli.parser import VirtualEnvConfigParser as VirtualEnvConfigParser
from virtualenv.config.cli.parser import VirtualEnvOptions as VirtualEnvOptions
from virtualenv.report import LEVELS as LEVELS
from virtualenv.report import setup_report as setup_report
from virtualenv.seed.wheels.periodic_update import manual_upgrade as manual_upgrade
from virtualenv.version import __version__ as __version__

from .cli import cli_run, session_via_cli
from .parser import add_version_flag as add_version_flag
from .parser import build_parser as build_parser
from .parser import build_parser_only as build_parser_only
from .parser import handle_extra_commands as handle_extra_commands
from .parser import load_app_data as load_app_data
from .plugin.activators import ActivationSelector as ActivationSelector
from .plugin.creators import CreatorSelector as CreatorSelector
from .plugin.discovery import get_discover as get_discover
from .plugin.seeders import SeederSelector as SeederSelector
from .session import Session as Session

__all__ = [
    "cli_run",
    "session_via_cli",
]
