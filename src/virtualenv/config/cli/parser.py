from __future__ import absolute_import, unicode_literals

from argparse import SUPPRESS, ArgumentDefaultsHelpFormatter, ArgumentParser

from virtualenv.seed.config import seed_package_args

from ..env_var import get_env_var
from ..ini import IniConfig
from .arguments import activation_args, base_args, create_args, make_method


class ArgumentParserWithEnvAndConfig(ArgumentParser):
    """
    Custom option parser which updates its defaults by checking the configuration files and environmental variables
    """

    def __init__(self, *args, **kwargs):
        self.file_config = IniConfig()
        kwargs["epilog"] = self.file_config.epilog
        super(ArgumentParserWithEnvAndConfig, self).__init__(*args, **kwargs)

    def fix_defaults(self):
        for action in self._actions:
            self.fix_default(action)

    def fix_default(self, action):
        if hasattr(action, "default") and hasattr(action, "dest") and action.default != SUPPRESS:
            as_type = type(action.default)
            outcome = get_env_var(action.dest, as_type)
            if outcome is None and self.file_config:
                outcome = self.file_config.get(action.dest, as_type)
            if outcome is not None:
                action.default, action.default_source = outcome


class HelpFormatter(ArgumentDefaultsHelpFormatter):
    def __init__(self, prog):
        super(HelpFormatter, self).__init__(prog, max_help_position=35, width=240)

    def _get_help_string(self, action):
        # noinspection PyProtectedMember
        text = super(HelpFormatter, self)._get_help_string(action)
        if hasattr(action, "default_source"):
            default = " (default: %(default)s)"
            if text.endswith(default):
                text = "{} (default: %(default)s -> from %(default_source)s)".format(text[: -len(default)])
        return text


def make_base_parser(options, parser=None):
    if parser is None:
        parser = ArgumentParserWithEnvAndConfig(add_help=False)
    base_args(options, parser)
    parser.fix_defaults()
    return parser


def make_core_parser(options):
    parser = ArgumentParserWithEnvAndConfig(prog="virtualenv", formatter_class=HelpFormatter)
    make_base_parser(options, parser)
    create_args(options, parser)
    make_method(options, parser)
    seed_package_args(options, parser)
    activation_args(options, parser)
    parser.fix_defaults()
    return parser
