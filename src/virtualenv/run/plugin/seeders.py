from __future__ import absolute_import, unicode_literals

from .base import ComponentBuilder


class SeederSelector(ComponentBuilder):
    def __init__(self, interpreter, parser):
        possible = self.options("virtualenv.seed")
        super(SeederSelector, self).__init__(interpreter, parser, "seeder", possible)

    def add_selector_arg_parse(self, name, choices):
        self.parser.add_argument(
            "--{}".format(name),
            choices=choices,
            default="app-data",
            required=False,
            help="seed packages install method",
        )
        self.parser.add_argument(
            "--without-pip",
            help="if set forces the none seeder, used for compatibility with venv",
            action="store_true",
            dest="without_pip",
        )

    def handle_selected_arg_parse(self, options):
        if options.without_pip is True:
            setattr(options, self.name, "none")
        return super(SeederSelector, self).handle_selected_arg_parse(options)

    def create(self, options):
        return self._impl_class(options)
