from __future__ import absolute_import, division, print_function

import posixpath

from virtualenv.flavors.base import BaseFlavor


class PosixFlavor(BaseFlavor):

    bin_dir = "bin"
    python_bin = "python"

    def core_modules(self, base_python):
        return super(PosixFlavor, self).core_modules(base_python) | set([
            # Directories
            "config",
            "plat-%s" % base_python["arch"]
        ])

    @property
    def activation_scripts(self):
        return set(["activate.sh", "activate.fish", "activate.csh"])

    def python_bins(self, version_info):
        return [
            "python%s" % ".".join(map(str, version_info[:i]))
            for i in range(3)
        ]

    def lib_dir(self, version_info):
        return posixpath.join(
            "lib",
            "python{0}.{1}".format(*version_info)
        )

    def include_dir(self, version_info):
        return posixpath.join(
            "include",
            "python{0}.{1}".format(*version_info)
        )
