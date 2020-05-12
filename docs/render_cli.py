from argparse import SUPPRESS
from collections import namedtuple
from contextlib import contextmanager

from docutils import nodes as n
from docutils.parsers.rst.directives import unchanged_required
from sphinx.util.docutils import SphinxDirective
from sphinxarg.parser import parse_parser

from virtualenv.run.plugin.base import ComponentBuilder

TableRow = namedtuple("TableRow", ["names", "default", "choices", "help"])

TextAsDefault = namedtuple("TextAsDefault", ["text"])

CUSTOM = {
    "discovery": ComponentBuilder.entry_points_for("virtualenv.discovery"),
    "creator": ComponentBuilder.entry_points_for("virtualenv.create"),
    "seeder": ComponentBuilder.entry_points_for("virtualenv.seed"),
    "activators": ComponentBuilder.entry_points_for("virtualenv.activate"),
}


class CliTable(SphinxDirective):
    name = "table_cli"
    option_spec = dict(module=unchanged_required, func=unchanged_required)

    def run(self):
        module_name, attr_name = self.options["module"], self.options["func"]
        parser_creator = getattr(__import__(module_name, fromlist=[attr_name]), attr_name)
        core_result = parse_parser(parser_creator())
        core_result["action_groups"] = [i for i in core_result["action_groups"] if i["title"] not in CUSTOM]

        content = []
        for i in core_result["action_groups"]:
            content.append(self._build_table(i["options"], i["title"], i["description"]))
        for key, name_to_class in CUSTOM.items():
            section = n.section("", ids=["section-{}".format(key)])
            title = n.title("", key)
            section += title
            self.state.document.note_implicit_target(title)
            content.append(section)
            results = {}

            for name, class_n in name_to_class.items():
                with self._run_parser(class_n, key, name):
                    cmd = ["--{}".format(key), name]
                    parser_result = parse_parser(parser_creator(cmd))
                    opt_group = next(i["options"] for i in parser_result["action_groups"] if i["title"] == key)
                    results[name] = opt_group
            core_names = set.intersection(*list({tuple(i["name"]) for i in v} for v in results.values()))
            if core_names:
                rows = [i for i in next(iter(results.values())) if tuple(i["name"]) in core_names]
                content.append(
                    self._build_table(rows, title="core", description="options shared across all {}".format(key)),
                )
            for name, group in results.items():
                rows = [i for i in group if tuple(i["name"]) not in core_names]
                if rows:
                    content.append(
                        self._build_table(rows, title=name, description="options specific to {} {}".format(key, name)),
                    )
        return content

    @contextmanager
    def _run_parser(self, class_n, key, name):
        test_name = {"creator": "can_create", "activators": "supports"}
        func_name = test_name.get(key)
        try:
            if func_name is not None:
                prev = getattr(class_n, func_name)

                def a(*args, **kwargs):
                    prev(*args, **kwargs)
                    if key == "activators":
                        return True
                    elif key == "creator":
                        if name == "venv":
                            from virtualenv.create.via_global_ref.venv import ViaGlobalRefMeta

                            meta = ViaGlobalRefMeta()
                            meta.symlink_error = None
                            return meta
                        from virtualenv.create.via_global_ref.builtin.via_global_self_do import BuiltinViaGlobalRefMeta

                        meta = BuiltinViaGlobalRefMeta()
                        meta.symlink_error = None
                        return meta
                    raise RuntimeError

                setattr(class_n, func_name, a)
            yield
        finally:
            if func_name is not None:
                # noinspection PyUnboundLocalVariable
                setattr(class_n, func_name, prev)

    def _build_table(self, options, title, description):
        table = n.table()
        table["classes"] += ["colwidths-auto"]

        options_group = n.tgroup(cols=3)
        table += options_group
        for _ in range(3):
            options_group += n.colspec()
        body = self._make_table_body(self.build_rows(options), title, description)
        options_group += body
        return table

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
                if isinstance(default, str) and default and default[0] == default[-1] and default[0] == '"':
                    default = default[1:-1]
                    if default == SUPPRESS:
                        default = None
            choices = option.get("choices")
            key = names[0].strip("-")
            if key in CliTable.plugins:
                choices = list(ComponentBuilder.entry_points_for(CliTable.plugins[key]).keys())
            help_text = option["help"]
            row = TableRow(names, default, choices, help_text)
            result.append(row)
        return result

    def _make_table_body(self, rows, title, description):
        t_body = n.tbody()
        header_row = n.paragraph()
        header_row += n.strong(text=title)
        if description:
            header_row += n.Text(" ⇒ ")
            header_row += n.Text(description)
        t_body += n.row("", n.entry("", header_row, morecols=2))
        for row in rows:
            name_list = self._get_targeted_names(row)
            default = CliTable._get_default(row)
            help_text = CliTable._get_help_text(row)
            row_node = n.row("", n.entry("", name_list), n.entry("", default), n.entry("", help_text))
            t_body += row_node
        return t_body

    def _get_targeted_names(self, row):
        names = [name.lstrip("-") for name in row.names]
        target = n.target("", "", ids=names, names=names)
        self.register_target_option(target)
        first = True
        for name, orig in zip(names, row.names):
            if first:
                first = False
            else:
                target += n.Text(", ")
            self_ref = n.reference(refid=name)
            self_ref += n.literal(text=orig)
            target += self_ref
        para = n.paragraph(text="")
        para += target
        return para

    @staticmethod
    def _get_help_text(row):
        name = row.names[0]
        if name in ("--creator",):
            content = row.help[: row.help.index("(") - 1]
        else:
            content = row.help
        if name in ("--setuptools", "--pip", "--wheel"):
            text = row.help
            at = text.index(" bundle ")
            help_body = n.paragraph("")
            help_body += n.Text(text[: at + 1])
            help_body += n.literal(text="bundle")
            help_body += n.Text(text[at + 7 :])
        else:
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
        elif name == "--app-data":
            default_body = n.Text("platform specific application data folder")
        elif name == "--activators":
            default_body = n.Text("comma separated list of activators supported")
        elif name == "--creator":
            default_body = n.paragraph("")
            default_body += n.literal(text="builtin")
            default_body += n.Text(" if exist, else ")
            default_body += n.literal(text="venv")
        else:
            if default is None:
                default_body = n.paragraph("", text="")
            else:
                default_body = n.literal(text=default if isinstance(default, str) else str(default))
        return default_body

    def register_target_option(self, target) -> None:
        domain = self.env.get_domain("std")
        self.state.document.note_explicit_target(target)
        for key in target["ids"]:
            domain.add_program_option(None, key, self.env.docname, key)


def literal_data(rawtext, app, type, slug, options):
    """Create a link to a BitBucket resource."""
    of_class = type.split(".")
    data = getattr(__import__(".".join(of_class[:-1]), fromlist=[of_class[-1]]), of_class[-1])
    return [n.literal("", text=",".join(data))], []


__all__ = (
    "CliTable",
    "literal_data",
)
