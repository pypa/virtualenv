from __future__ import absolute_import, division, print_function

import os.path

from virtualenv.flavors.base import BaseFlavor


class PosixFlavor(BaseFlavor):

    bin_dir = "bin"
    python_bin = "python"

    @property
    def activation_scripts(self):
        return {"activate.sh", "activate.fish", "activate.csh"}

    def python_bins(self, version_info):
        return [
            "python{}".format(".".join(map(str, version_info[:i])))
            for i in range(3)
        ]

    def lib_dir(self, version_info):
        return os.path.join(
            "lib",
            "python{}".format(
                ".".join(map(str, version_info[:2]))
            ),
        )
