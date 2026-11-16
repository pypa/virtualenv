"""What virtualenv adds to the SBOMs of its wheel and zipapp; the python-sbom content-provider option names it."""

from __future__ import annotations

import ast
import json
from pathlib import PurePosixPath
from typing import TYPE_CHECKING

from python_sbom import BundledWheelInfo, ContentProvider

if TYPE_CHECKING:
    from python_sbom import Property, ProviderContext


class VirtualenvContent(ContentProvider):
    def bundled_wheel(self, context: ProviderContext, wheel: PurePosixPath) -> BundledWheelInfo:
        # virtualenv bundles only PyPA's own projects, so virtualenv's supplier supplies them too
        if wheel.suffix == ".whl":
            return BundledWheelInfo(properties=self._seeded(context, wheel), supplier=context.settings.supplier)
        return BundledWheelInfo(properties=self._loaded(context, wheel), supplier=context.settings.supplier)

    @staticmethod
    def _seeded(context: ProviderContext, wheel: PurePosixPath) -> list[Property]:
        # the BUNDLE_SUPPORT table in __init__.py names the Python versions that seed each embedded wheel; it is read by
        # name, without importing the package
        module = ast.parse(context.read(wheel.parent / "__init__.py").decode("utf-8"))
        support: dict[str, dict[str, str]] = ast.literal_eval(
            next(
                node.value
                for node in module.body
                if isinstance(node, ast.AnnAssign)
                and isinstance(node.target, ast.Name)
                and node.target.id == "BUNDLE_SUPPORT"
            )
        )
        return [
            {"name": f"{context.identity.property_prefix}:seeded-for-python", "value": python}
            for python, wheels in support.items()
            if wheel.name in wheels.values()
        ]

    @staticmethod
    def _loaded(context: ProviderContext, directory: PurePosixPath) -> list[Property]:
        # tasks/make_zipapp.py writes distributions.json, naming the .dist-info each Python loads from the zipapp
        loaded = json.loads(context.read(PurePosixPath("distributions.json")))
        return [
            {"name": f"{context.identity.property_prefix}:loaded-for-python", "value": python}
            for python, platforms in loaded.items()
            if any(PurePosixPath(path).parent == directory for paths in platforms.values() for path in paths.values())
        ]
