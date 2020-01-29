from argparse import SUPPRESS
from collections import namedtuple

from docutils import nodes as n
from docutils.parsers.rst import Directive
from docutils.parsers.rst.directives import unchanged
from sphinxarg.parser import parse_parser

from virtualenv.run.plugin.base import ComponentBuilder

TableRow = namedtuple("TableRow", ["names", "default", "choices", "help"])

TextAsDefault = namedtuple("TextAsDefault", ["text"])


class Cli(Directive):
    has_content = False
    option_spec = dict(module=unchanged, func=unchanged, prog=unchanged, noepilog=unchanged, nodescription=unchanged,)

    def run(self):
        module_name, attr_name = self.options["module"], self.options["func"]
        parser = getattr(__import__(module_name, fromlist=[attr_name]), attr_name)()
        result = parse_parser(parser)
        table = n.table()
        for i in result["action_groups"]:
            group = self.make_table(result["prog"], rows=self.build_rows(i["options"]))
            table += group
        return [table]

    plugins = {
        "creator": "virtualenv.create",
        "seed": "virtualenv.seed",
        "activators": "virtualenv.activate",
        "discovery": "virtualenv.discovery",
    }

    @staticmethod
    def build_rows(options):
        result = []
        for option in options:
            names = option["name"]
            default = option["default"]
            if default is not None:
                if isinstance(default, str) and default[0] == default[-1] and default[0] == '"':
                    default = default[1:-1]
                    if default == SUPPRESS:
                        default = None
            choices = option.get("choices")
            key = names[0].strip("-")
            if key in Cli.plugins:
                choices = list(ComponentBuilder.entry_points_for(Cli.plugins[key]).keys())
            help_text = option["help"]
            row = TableRow(names, default, choices, help_text)
            result.append(row)
        return result

    @staticmethod
    def make_table(prog, rows):
        t_body = n.tbody()
        for row in rows:
            ref, refs = Cli._get_named_ref(prog, row)
            default = Cli._get_default(row)
            help_text = Cli._get_help_text(row)
            t_body += n.row("", n.entry("", ref), n.entry("", default), n.entry("", help_text), ids=refs,)
        group = n.tgroup(cols=4)
        group += n.colspec(colwidth=1.5)
        group += n.colspec(colwidth=1.5)
        group += n.colspec(colwidth=8)
        group += n.thead("", n.row("", *[n.entry("", n.line(text=c)) for c in ["name", "default", "help"]]))
        group += t_body
        return group

    @staticmethod
    def _get_named_ref(prog, row):
        refs, name_nodes = [], []
        ref = n.paragraph("", "")
        first = True
        for name in row.names:
            if not first:
                ref.append(n.Text(", "))
            else:
                first = False
            ref_key = "{}{}".format(prog, name)
            ref_node = n.reference("", "", refid=ref_key)
            ref_node += n.literal(text=name)
            ref += ref_node
            refs.append(ref_key)
        return ref, refs

    @staticmethod
    def _get_help_text(row):
        if row.names[0] == "--creator":
            content = row.help[: row.help.index("(") - 1]
        else:
            content = row.help
        help_body = n.paragraph("", "", n.Text(content))
        if row.choices is not None:
            help_body += n.Text("; choice of: ")
            first = True
            for choice in row.choices:
                if first:
                    first = False
                else:
                    help_body += n.Text(", ")
                help_body += n.literal(text=choice)
        return help_body

    @staticmethod
    def _get_default(row):
        default = row.default
        name = row.names[0]
        if name == "-p":
            default_body = n.Text("the python executable virtualenv is installed into")
        elif name == "--activators":
            default_body = n.Text("comma separated list of activators supported")
        elif name == "--creator":
            default_body = n.paragraph("")
            default_body += n.literal(text="builtin")
            default_body += n.Text(" if possible, ")
            default_body += n.literal(text="venv")
            default_body += n.Text(" otherwise")
        else:
            if default is None:
                default_body = n.paragraph("", text="")
            else:
                default_body = n.literal(text=default if isinstance(default, str) else str(default))
        return default_body


def literal_data(rawtext, app, type, slug, options):
    """Create a link to a BitBucket resource."""
    of_class = type.split(".")
    data = getattr(__import__(".".join(of_class[:-1]), fromlist=[of_class[-1]]), of_class[-1])
    return [n.literal("", text=",".join(data))], []


__all__ = (
    "Cli",
    "literal_data",
)
