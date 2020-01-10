from __future__ import absolute_import, unicode_literals

from virtualenv.interpreters.create.venv import Venv

from .base import ComponentBuilder


class CreatorSelector(ComponentBuilder):
    def __init__(self, interpreter, parser):
        super(CreatorSelector, self).__init__(interpreter, parser, "virtualenv.create", "creator", True)

    def _build_options(self, options):
        if not options:
            raise RuntimeError("No virtualenv implementation for {}".format(self.interpreter))

        from virtualenv.interpreters.create.builtin_way import VirtualenvBuiltin

        self.builtin_way = next((i for i, v in options.items() if issubclass(v, VirtualenvBuiltin)), None)
        if self.builtin_way is not None:
            options["builtin"] = options[self.builtin_way]  # make the first builtin method the builtin alias
        return options

    def add_selector_arg_parse(self, name, choices):
        # prefer the built-in venv if present, otherwise fallback to first defined type
        choices = sorted(choices, key=lambda a: 0 if a == "venv" else 1)
        self.parser.add_argument(
            "--{}".format(name),
            choices=choices,
            default=next(iter(choices)),
            required=False,
            help="create environment via{}".format(
                "" if self.builtin_way is None else " (builtin = {})".format(self.builtin_way)
            ),
        )

    def create(self, options):
        if issubclass(self._impl_class, Venv):
            options.builtin_way = (
                None if self.builtin_way is None else self.possible[self.builtin_way](options, self.interpreter)
            )
        return super(CreatorSelector, self).create(options)
