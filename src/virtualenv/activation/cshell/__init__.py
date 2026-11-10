from __future__ import annotations

from virtualenv.activation.via_template import ViaTemplateActivator as ViaTemplateActivator
from virtualenv.util.text import collapse_line_boundaries as collapse_line_boundaries

from .activator import CShellActivator

__all__ = [
    "CShellActivator",
]
