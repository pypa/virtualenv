import sys

class _Finder:
    fullname = None
    lock = []

    def find_spec(self, fullname, path, target=None):
        # This should handle the NameError gracefully
        try:
            distutils_patch = _DISTUTILS_PATCH  # noqa: F821
        except NameError:
            return None
        if fullname in distutils_patch and self.fullname is None:
            return None
        return None

    @staticmethod
    def exec_module(old, module):
        old(module)
        try:
            distutils_patch = _DISTUTILS_PATCH  # noqa: F821
        except NameError:
            return
        if module.__name__ in distutils_patch:
            pass  # Would call patch_dist(module)

    @staticmethod
    def load_module(old, name):
        module = old(name)
        try:
            distutils_patch = _DISTUTILS_PATCH  # noqa: F821
        except NameError:
            return module
        if module.__name__ in distutils_patch:
            pass  # Would call patch_dist(module)
        return module

finder = _Finder()
