from __future__ import absolute_import, division, print_function

import os.path

from virtualenv.flavors.base import BaseFlavor


class WindowsFlavor(BaseFlavor):

    bin_dir = "Scripts"
    python_bin = "python.exe"

    @property
    def activation_scripts(self):
        return set(["activate.bat", "activate.ps1", "deactivate.bat"])

    def python_bins(self, python_info):
        version_info = python_info["sys.version_info"]
        return [
            "python{0}.exe".format(".".join(map(str, version_info[:i])))
            for i in range(3)
        ]

    def lib_dir(self, python_info):
        return "Lib"

    def include_dir(self, python_info):
        return "include"
