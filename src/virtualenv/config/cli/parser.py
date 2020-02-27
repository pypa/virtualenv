from __future__ import absolute_import, unicode_literals

from argparse import SUPPRESS, ArgumentDefaultsHelpFormatter, ArgumentParser

from virtualenv.config.convert import get_type

from ..env_var import get_env_var
from ..ini import IniConfig


class VirtualEnvConfigParser(ArgumentParser):
    """
    Custom option parser which updates its defaults by checking the configuration files and environmental variables
    """

    def __init__(self, options=None, *args, **kwargs):
        self.file_config = IniConfig()
        self.epilog_list = []
        kwargs["epilog"] = self.file_config.epilog
        kwargs["add_help"] = False
        kwargs["formatter_class"] = HelpFormatter
        kwargs["prog"] = "virtualenv"
        super(VirtualEnvConfigParser, self).__init__(*args, **kwargs)
        self._fixed = set()
        self._elements = None
        self._verbosity = None
        self._options = options
        self._interpreter = None
        self._app_data = None

    def _fix_defaults(self):
        for action in self._actions:
            action_id = id(action)
            if action_id not in self._fixed:
                self._fix_default(action)
                self._fixed.add(action_id)

    def _fix_default(self, action):
        if hasattr(action, "default") and hasattr(action, "dest") and action.default != SUPPRESS:
            as_type = get_type(action)
            outcome = get_env_var(action.dest, as_type)
            if outcome is None and self.file_config:
                outcome = self.file_config.get(action.dest, as_type)
            if outcome is not None:
                action.default, action.default_source = outcome

    def enable_help(self):
        self._fix_defaults()
        self.add_argument("-h", "--help", action="help", default=SUPPRESS, help="show this help message and exit")

    def parse_known_args(self, args=None, namespace=None):
        self._fix_defaults()
        return super(VirtualEnvConfigParser, self).parse_known_args(args, namespace=namespace)

    def parse_args(self, args=None, namespace=None):
        self._fix_defaults()
        return super(VirtualEnvConfigParser, self).parse_args(args, namespace=namespace)


class HelpFormatter(ArgumentDefaultsHelpFormatter):
    def __init__(self, prog):
        super(HelpFormatter, self).__init__(prog, max_help_position=32, width=240)

    def _get_help_string(self, action):
        # noinspection PyProtectedMember
        text = super(HelpFormatter, self)._get_help_string(action)
        if hasattr(action, "default_source"):
            default = " (default: %(default)s)"
            if text.endswith(default):
                text = "{} (default: %(default)s -> from %(default_source)s)".format(text[: -len(default)])
        return text
