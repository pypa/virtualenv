from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

from virtualenv.version import __version__

company = "PyPA"
name = "virtualenv"
version = ".".join(__version__.split(".")[:2])
release = __version__
copyright = f"2007-{datetime.now(tz=timezone.utc).year}, {company}, PyPA"  # noqa: A001

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.autosectionlabel",
    "sphinx.ext.extlinks",
    "sphinx.ext.intersphinx",
    "sphinx_autodoc_typehints",
    "sphinx_copybutton",
    "sphinx_inline_tabs",
    "sphinxcontrib.mermaid",
    "sphinxcontrib.towncrier.ext",
]

intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
}

towncrier_draft_autoversion_mode = "draft"
towncrier_draft_include_empty = True
towncrier_draft_working_directory = Path(__file__).parent.parent

templates_path = []
unused_docs = []
source_suffix = ".rst"
exclude_patterns = ["_build", "changelog/*", "_draft.rst"]

main_doc = "index"
pygments_style = "default"
always_document_param_types = True
project = name
today_fmt = "%B %d, %Y"

html_theme = "furo"
html_title, html_last_updated_fmt = project, datetime.now(tz=timezone.utc).isoformat()
pygments_style, pygments_dark_style = "sphinx", "monokai"
html_static_path = ["_static"]
html_css_files = ["custom.css"]
html_js_files = ["rtd-search.js"]
html_favicon = "_static/virtualenv.svg"
html_theme_options = {
    "light_logo": "virtualenv.png",
    "dark_logo": "virtualenv.png",
    "sidebar_hide_name": True,
}
html_show_sourcelink = False

autoclass_content = "both"  # Include __init__ in class documentation
autodoc_member_order = "bysource"
autosectionlabel_prefix_document = True

extlinks = {
    "issue": ("https://github.com/pypa/virtualenv/issues/%s", "#%s"),
    "pull": ("https://github.com/pypa/virtualenv/pull/%s", "PR #%s"),
    "user": ("https://github.com/%s", "@%s"),
    "pypi": ("https://pypi.org/project/%s", "%s"),
}


def setup(app):
    doc_tree = Path(app.doctreedir)
    for name in ("cli_interface", "reference/cli"):
        doctree = doc_tree / f"{name}.doctree"
        if doctree.exists():
            doctree.unlink()

    here = Path(__file__).parent
    if str(here) not in sys.path:
        sys.path.append(str(here))

    from render_cli import CliTable, literal_data  # noqa: PLC0415

    app.add_css_file("custom.css")
    app.add_directive(CliTable.name, CliTable)
    app.add_role("literal_data", literal_data)
