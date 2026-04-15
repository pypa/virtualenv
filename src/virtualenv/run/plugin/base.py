from __future__ import annotations

import sys
from collections import OrderedDict
from importlib.metadata import entry_points

importlib_metadata_version = ()


class PluginLoader:
    _OPTIONS = None
    _ENTRY_POINTS = None

    @classmethod
    def entry_points_for(cls, key):
        if sys.version_info >= (3, 10) or importlib_metadata_version >= (3, 6):
            selected = list(cls.entry_points().select(group=key))
        else:
            selected = list(cls.entry_points().get(key, []))
        # Third-party packages may register entry points with the same name as virtualenv's
        # built-ins (e.g. xonsh's own `virtualenv.activate.xonsh`). Sort so built-ins are
        # inserted last into the OrderedDict, making them win on name collision.
        selected.sort(key=lambda e: e.value.startswith("virtualenv."))
        return OrderedDict((e.name, e.load()) for e in selected)

    @staticmethod
    def entry_points():
        if PluginLoader._ENTRY_POINTS is None:
            PluginLoader._ENTRY_POINTS = entry_points()
        return PluginLoader._ENTRY_POINTS


class ComponentBuilder(PluginLoader):
    def __init__(self, interpreter, parser, name, possible) -> None:
        self.interpreter = interpreter
        self.name = name
        self._impl_class = None
        self.possible = possible
        self.parser = parser.add_argument_group(title=name)
        self.add_selector_arg_parse(name, list(self.possible))

    @classmethod
    def options(cls, key):
        if cls._OPTIONS is None:
            cls._OPTIONS = cls.entry_points_for(key)
        return cls._OPTIONS

    def add_selector_arg_parse(self, name, choices):
        raise NotImplementedError

    def handle_selected_arg_parse(self, options):
        selected = getattr(options, self.name)
        if selected not in self.possible:
            msg = f"No implementation for {self.interpreter}"
            raise RuntimeError(msg)
        self._impl_class = self.possible[selected]
        self.populate_selected_argparse(selected, options.app_data)
        return selected

    def populate_selected_argparse(self, selected, app_data):
        self.parser.description = f"options for {self.name} {selected}"
        self._impl_class.add_parser_arguments(self.parser, self.interpreter, app_data)

    def create(self, options):
        return self._impl_class(options, self.interpreter)


__all__ = [
    "ComponentBuilder",
    "PluginLoader",
]
