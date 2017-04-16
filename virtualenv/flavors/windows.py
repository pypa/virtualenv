from __future__ import absolute_import, division, print_function

import os.path

from virtualenv.flavors.base import BaseFlavor


class WindowsFlavor(BaseFlavor):

    bin_dir = "Scripts"
    python_bin = "python.exe"

    def bootstrap_modules(self, base_python):
        return super(WindowsFlavor, self).bootstrap_modules(base_python) | set(["ntpath.py"])

    @property
    def activation_scripts(self):
        return set(["activate.bat", "activate.ps1", "deactivate.bat"])

    def python_bins(self, base_python):
        version_info = base_python["sys.version_info"]
        return [
            "python{0}.exe".format(".".join(map(str, version_info[:i])))
            for i in range(3)
        ]

    def lib_dir(self, base_python):
        return "Lib"

    def include_dir(self, base_python):
        return "include"
