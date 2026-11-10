from __future__ import annotations

import sys

if sys.version_info >= (3, 11):
    from python_sbom.hatch import SbomBuildHook
else:  # python-sbom needs Python 3.11, so builds on older interpreters carry no SBOM
    from hatchling.builders.hooks.plugin.interface import BuildHookInterface as SbomBuildHook


def get_build_hook() -> type[SbomBuildHook]:
    # the content-provider option in [tool.python-sbom] adds what virtualenv knows about the wheels it embeds
    return SbomBuildHook
