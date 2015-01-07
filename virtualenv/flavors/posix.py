from __future__ import absolute_import, division, print_function

import posixpath

from virtualenv.flavors.base import BaseFlavor


class PosixFlavor(BaseFlavor):

    bin_dir = "bin"
    python_bin = "python"

    def bootstrap_modules(self, base_python):
        return super(PosixFlavor, self).bootstrap_modules(base_python) | set([
            # Directories
        ])

    @property
    def activation_scripts(self):
        return set(["activate.sh", "activate.fish", "activate.csh"])

    def python_bins(self, base_python):
        version_info = base_python["sys.version_info"]
        return [
            "python%s" % ".".join(map(str, version_info[:i]))
            for i in range(3)
        ]

    def lib_dir(self, base_python):
        return posixpath.join(
            "lib",
            "python{0}.{1}".format(*base_python["sys.version_info"])
        )

    def include_dir(self, base_python):
        if base_python["is_pypy"]:
            return "include"
        else:
            return posixpath.join(
                "include",
                "python{1}.{2}{0}".format(base_python["sys.abiflags"], *base_python["sys.version_info"])
            )
