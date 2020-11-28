import subprocess
import sys
from datetime import date, datetime
from pathlib import Path

from virtualenv.version import __version__

company = "PyPA"
name = "virtualenv"
version = ".".join(__version__.split(".")[:2])
release = __version__
copyright = f"2007-{date.today().year}, {company}, PyPA"

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.autosectionlabel",
    "sphinx.ext.extlinks",
]

templates_path = []
unused_docs = []
source_suffix = ".rst"
exclude_patterns = ["_build", "changelog/*", "_draft.rst"]

main_doc = "index"
pygments_style = "default"
always_document_param_types = True
project = name
today_fmt = "%B %d, %Y"

html_title = "virtualenv"
html_theme = "furo"
html_static_path = ["_static"]
html_last_updated_fmt = datetime.now().isoformat()
htmlhelp_basename = "Pastedoc"
autoclass_content = "both"  # Include __init__ in class documentation
autodoc_member_order = "bysource"
autosectionlabel_prefix_document = True

extlinks = {
    "issue": ("https://github.com/pypa/virtualenv/issues/%s", "#"),
    "pull": ("https://github.com/pypa/virtualenv/pull/%s", "PR #"),
    "user": ("https://github.com/%s", "@"),
    "pypi": ("https://pypi.org/project/%s", ""),
}


def generate_draft_news():
    root = Path(__file__).parents[1]
    new = subprocess.check_output(
        [sys.executable, "-m", "towncrier", "--draft", "--version", "NEXT"],
        cwd=root,
        universal_newlines=True,
    )
    (root / "docs" / "_draft.rst").write_text("" if "No significant changes" in new else new)


generate_draft_news()


def setup(app):
    # the CLI arguments are dynamically generated
    doc_tree = Path(app.doctreedir)
    cli_interface_doctree = doc_tree / "cli_interface.doctree"
    if cli_interface_doctree.exists():
        cli_interface_doctree.unlink()

    HERE = Path(__file__).parent
    if str(HERE) not in sys.path:
        sys.path.append(str(HERE))

    # noinspection PyUnresolvedReferences
    from render_cli import CliTable, literal_data

    app.add_css_file("custom.css")
    app.add_directive(CliTable.name, CliTable)
    app.add_role("literal_data", literal_data)
