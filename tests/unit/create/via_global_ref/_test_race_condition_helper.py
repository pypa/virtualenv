from __future__ import annotations

from typing import ClassVar


class _Finder:
    fullname = None
    lock: ClassVar[list] = []

    def find_spec(self, fullname, path, target=None):  # noqa: ARG002
        # This should handle the NameError gracefully
        try:
            distutils_patch = _DISTUTILS_PATCH
        except NameError:
            return
        if fullname in distutils_patch and self.fullname is None:
            return
        return

    @staticmethod
    def exec_module(old, module):
        old(module)
        try:
            distutils_patch = _DISTUTILS_PATCH
        except NameError:
            return
        if module.__name__ in distutils_patch:
            pass  # Would call patch_dist(module)

    @staticmethod
    def load_module(old, name):
        module = old(name)
        try:
            distutils_patch = _DISTUTILS_PATCH
        except NameError:
            return module
        if module.__name__ in distutils_patch:
            pass  # Would call patch_dist(module)
        return module


finder = _Finder()
