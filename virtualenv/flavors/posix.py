from __future__ import absolute_import, division, print_function

import posixpath

from virtualenv.flavors.base import BaseFlavor


class PosixFlavor(BaseFlavor):

    def bin_dir(self, python_info):
        return "bin"

    python_bin = "python"

    @property
    def activation_scripts(self):
        return set(["activate.sh", "activate.fish", "activate.csh"])

    def python_bins(self, python_info):
        version_info = python_info["sys.version_info"]
        return [
            "python%s" % ".".join(map(str, version_info[:i]))
            for i in range(3)
        ]

    def extra_bins(self, python_info):
        return []

    def lib_dir(self, python_info):
        return posixpath.join(
            "lib",
            "python{0}.{1}".format(*python_info["sys.version_info"])
        )

    def include_dir(self, python_info):
        if python_info["is_pypy"]:
            return "include"
        else:
            return posixpath.join(
                "include",
                "python{1}.{2}{0}".format(python_info["sys.abiflags"], *python_info["sys.version_info"])
            )
