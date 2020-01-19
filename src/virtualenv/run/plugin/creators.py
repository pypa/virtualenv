from __future__ import absolute_import, unicode_literals

from collections import OrderedDict

from virtualenv.create.describe import Describe
from virtualenv.create.via_global_ref.builtin.builtin_way import VirtualenvBuiltin

from .base import ComponentBuilder


class CreatorSelector(ComponentBuilder):
    def __init__(self, interpreter, parser):
        creators = OrderedDict()
        self.describe = None
        self.builtin_key = None
        self.can_create_results = {}
        for key, creator_class in self.options("virtualenv.create").items():
            if key == "builtin":
                raise RuntimeError("builtin creator is a reserved name")
            meta = creator_class.can_create(interpreter)
            if meta:
                if "builtin" not in creators and issubclass(creator_class, VirtualenvBuiltin):
                    self.builtin_key = key
                    creators["builtin"] = creator_class
                    self.can_create_results["builtin"] = meta
                creators[key] = creator_class
                self.can_create_results[key] = meta
            if (
                self.describe is None
                and issubclass(creator_class, Describe)
                and creator_class.can_describe(interpreter)
            ):
                self.describe = creator_class
        if not creators:
            raise RuntimeError("No virtualenv implementation for {}".format(interpreter))
        super(CreatorSelector, self).__init__(interpreter, parser, "creator", creators)

    def add_selector_arg_parse(self, name, choices):
        # prefer the built-in venv if present, otherwise fallback to first defined type
        choices = sorted(choices, key=lambda a: 0 if a == "venv" else 1)
        self.parser.add_argument(
            "--{}".format(name),
            choices=choices,
            default=next(iter(choices)),
            required=False,
            help="create environment via{}".format(
                "" if self.builtin_key is None else " (builtin = {})".format(self.builtin_key)
            ),
        )

    def populate_selected_argparse(self, selected):
        self._impl_class.add_parser_arguments(self.parser, self.interpreter, self.can_create_results[selected])

    def create(self, options):
        options.meta = self.can_create_results[getattr(options, self.name)]
        if not issubclass(self._impl_class, Describe):
            options.describe = self.describe(options, self.interpreter)
        return super(CreatorSelector, self).create(options)
