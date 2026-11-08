"""The licenses virtualenv accepts for what its wheel and zipapp ship."""

from __future__ import annotations

from typing import Final

# the licensing policy in docs/development.rst refers to this set; tasks/validate_sbom.py hands it to python-sbom
# validate
ALLOWED_LICENSES: Final[frozenset[str]] = frozenset({
    "Apache-2.0",
    "BSD-2-Clause",
    "BSD-3-Clause",
    "ISC",
    "MIT",
    "PSF-2.0",
    "Unlicense",
})

__all__ = [
    "ALLOWED_LICENSES",
]
