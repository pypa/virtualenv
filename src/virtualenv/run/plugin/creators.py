from __future__ import absolute_import, unicode_literals

from collections import OrderedDict, namedtuple

from virtualenv.create.describe import Describe
from virtualenv.create.via_global_ref.builtin.builtin_way import VirtualenvBuiltin

from .base import ComponentBuilder

CreatorInfo = namedtuple("CreatorInfo", ["key_to_class", "key_to_meta", "describe", "builtin_key"])


class CreatorSelector(ComponentBuilder):
    def __init__(self, interpreter, parser):
        creators, self.key_to_meta, self.describe, self.builtin_key = self.for_interpreter(interpreter)
        if not creators:
            raise RuntimeError("No virtualenv implementation for {}".format(interpreter))
        super(CreatorSelector, self).__init__(interpreter, parser, "creator", creators)

    @classmethod
    def for_interpreter(cls, interpreter):
        key_to_class, key_to_meta, builtin_key, describe = OrderedDict(), {}, None, None
        for key, creator_class in cls.options("virtualenv.create").items():
            if key == "builtin":
                raise RuntimeError("builtin creator is a reserved name")
            meta = creator_class.can_create(interpreter)
            if meta:
                if "builtin" not in key_to_class and issubclass(creator_class, VirtualenvBuiltin):
                    builtin_key = key
                    key_to_class["builtin"] = creator_class
                    key_to_meta["builtin"] = meta
                key_to_class[key] = creator_class
                key_to_meta[key] = meta
            if describe is None and issubclass(creator_class, Describe) and creator_class.can_describe(interpreter):
                describe = creator_class
        return CreatorInfo(
            key_to_class=key_to_class, key_to_meta=key_to_meta, describe=describe, builtin_key=builtin_key
        )

    def add_selector_arg_parse(self, name, choices):
        # prefer the built-in venv if present, otherwise fallback to first defined type
        choices = sorted(choices, key=lambda a: 0 if a == "builtin" else 1)
        default_value = self._get_default(choices)
        self.parser.add_argument(
            "--{}".format(name),
            choices=choices,
            default=default_value,
            required=False,
            help="create environment via{}".format(
                "" if self.builtin_key is None else " (builtin = {})".format(self.builtin_key)
            ),
        )

    @staticmethod
    def _get_default(choices):
        return next(iter(choices))

    def populate_selected_argparse(self, selected):
        self.parser.description = "options for {} {}".format(self.name, selected)
        self._impl_class.add_parser_arguments(self.parser, self.interpreter, self.key_to_meta[selected])

    def create(self, options):
        options.meta = self.key_to_meta[getattr(options, self.name)]
        if not issubclass(self._impl_class, Describe):
            options.describe = self.describe(options, self.interpreter)
        return super(CreatorSelector, self).create(options)
