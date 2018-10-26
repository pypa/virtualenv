# -*- coding: utf-8 -*-
import os

on_rtd = os.environ.get("READTHEDOCS", None) == "True"
extensions = ["sphinx.ext.autodoc", "sphinx.ext.extlinks"]
source_suffix = ".rst"
master_doc = "index"
project = "virtualenv"
copyright = "2007-2018, Ian Bicking, The Open Planning Project, PyPA"


try:
    from virtualenv import __version__

    # The short X.Y version.
    version = ".".join(__version__.split(".")[:2])
    # The full version, including alpha/beta/rc tags.
    release = __version__
except ImportError:
    version = release = "dev"

today_fmt = "%B %d, %Y"
unused_docs = []
pygments_style = "sphinx"

extlinks = {
    "issue": ("https://github.com/pypa/virtualenv/issues/%s", "#"),
    "pull": ("https://github.com/pypa/virtualenv/pull/%s", "PR #"),
}

html_theme = "default"
if not on_rtd:
    try:
        import sphinx_rtd_theme

        html_theme = "sphinx_rtd_theme"
        html_theme_path = [sphinx_rtd_theme.get_html_theme_path()]
    except ImportError:
        pass
html_last_updated_fmt = "%b %d, %Y"
htmlhelp_basename = "Pastedoc"
