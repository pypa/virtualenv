from __future__ import annotations

import subprocess
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

html_theme = "furo"
html_title, html_last_updated_fmt = project, datetime.now(tz=timezone.utc).isoformat()
pygments_style, pygments_dark_style = "sphinx", "monokai"
html_static_path, html_css_files = ["_static"], ["custom.css"]

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
    here = Path(__file__).parent
    root, exe = here.parent, Path(sys.executable)
    towncrier = exe.with_name(f"towncrier{exe.suffix}")
    cmd = [str(towncrier), "build", "--draft", "--version", "NEXT"]
    new = subprocess.check_output(cmd, cwd=root, text=True, stderr=subprocess.DEVNULL, encoding="UTF-8")  # noqa: S603
    (root / "docs" / "_draft.rst").write_text("" if "No significant changes" in new else new, encoding="UTF-8")

    # the CLI arguments are dynamically generated
    doc_tree = Path(app.doctreedir)
    cli_interface_doctree = doc_tree / "cli_interface.doctree"
    if cli_interface_doctree.exists():
        cli_interface_doctree.unlink()

    here = Path(__file__).parent
    if str(here) not in sys.path:
        sys.path.append(str(here))

    # noinspection PyUnresolvedReferences
    from render_cli import CliTable, literal_data

    app.add_css_file("custom.css")
    app.add_directive(CliTable.name, CliTable)
    app.add_role("literal_data", literal_data)
