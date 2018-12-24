from __future__ import absolute_import, unicode_literals
import os
import re
import subprocess
import sys
from virtualenv import __version__
from pathlib import Path
extensions = ["sphinx.ext.autodoc", "sphinx.ext.extlinks"]
source_suffix = ".rst"
master_doc = "index"
project = "virtualenv"
copyright = "2007-2018, Ian Bicking, The Open Planning Project, PyPA"

ROOT_SRC_TREE_DIR = Path(__file__).parents[1]


def generate_draft_news():
    home = "https://github.com"
    issue = "{}/issue".format(home)
    fragments_path = ROOT_SRC_TREE_DIR / "docs" / "changelog"
    for pattern, replacement in (
        (r"[^`]@([^,\s]+)", r"`@\1 <{}/\1>`_".format(home)),
        (r"[^`]#([\d]+)", r"`#pr\1 <{}/\1>`_".format(issue)),
    ):
        for path in fragments_path.glob("*.rst"):
            path.write_text(re.sub(pattern, replacement, path.read_text()))
    env = os.environ.copy()
    env["PATH"] += os.pathsep.join([os.path.dirname(sys.executable)] + env["PATH"].split(os.pathsep))
    changelog = subprocess.check_output(
        ["towncrier", "--draft", "--version", "DRAFT"], cwd=str(ROOT_SRC_TREE_DIR), env=env
    ).decode("utf-8")
    if "No significant changes" in changelog:
        content = ""
    else:
        note = "*Changes in master, but not released yet are under the draft section*."
        content = "{}\n\n{}".format(note, changelog)
    (ROOT_SRC_TREE_DIR / "docs" / "_draft.rst").write_text(content)


generate_draft_news()

version = ".".join(__version__.split(".")[:2])
release = __version__

today_fmt = "%B %d, %Y"
unused_docs = []
pygments_style = "sphinx"

extlinks = {
    "issue": ("https://github.com/pypa/virtualenv/issues/%s", "#"),
    "pull": ("https://github.com/pypa/virtualenv/pull/%s", "PR #"),
}

html_theme = "default"
on_rtd = os.environ.get("READTHEDOCS", None) == "True"
if not on_rtd:
    try:
        import sphinx_rtd_theme

        html_theme = "sphinx_rtd_theme"
        html_theme_path = [sphinx_rtd_theme.get_html_theme_path()]
    except ImportError:
        pass
html_last_updated_fmt = "%b %d, %Y"
htmlhelp_basename = "Pastedoc"
