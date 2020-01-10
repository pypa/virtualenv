from __future__ import absolute_import, unicode_literals

import sys
from collections import OrderedDict

if sys.version_info >= (3, 8):
    from importlib.metadata import entry_points
else:
    from importlib_metadata import entry_points


class PluginLoader(object):
    _OPTIONS = None
    _ENTRY_POINTS = None

    @classmethod
    def entry_points_for(cls, key):
        return OrderedDict((e.name, e.load()) for e in cls.entry_points().get(key, {}))

    @staticmethod
    def entry_points():
        if PluginLoader._ENTRY_POINTS is None:
            PluginLoader._ENTRY_POINTS = entry_points()
        return PluginLoader._ENTRY_POINTS


class ComponentBuilder(PluginLoader):
    def __init__(self, interpreter, parser, key, name, needs_support):
        self.interpreter = interpreter
        self.name = name
        self._impl_class = None
        opts = self.options(key)
        self.possible = self._build_options(
            OrderedDict((k, v) for k, v in opts.items() if v.supports(interpreter)) if needs_support else opts
        )
        self.parser = parser.add_argument_group("{} options".format(name))
        self.add_selector_arg_parse(name, list(self.possible))

    @classmethod
    def options(cls, key):
        if cls._OPTIONS is None:
            cls._OPTIONS = cls.entry_points_for(key)
        return cls._OPTIONS

    def add_selector_arg_parse(self, name, choices):
        raise NotImplementedError

    def _build_options(self, options):
        return options

    def handle_selected_arg_parse(self, options):
        selected = getattr(options, self.name)
        if selected not in self.possible:
            raise RuntimeError("No implementation for {}".format(self.interpreter))
        self._impl_class = self.possible[selected]
        self._impl_class.add_parser_arguments(self.parser, self.interpreter)
        return selected

    def create(self, options):
        return self._impl_class(options, self.interpreter)
