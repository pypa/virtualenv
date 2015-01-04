import os

from virtualenv.flavors.base import BaseFlavor


class Flavor(BaseFlavor):
    bin_dir = "Scripts"
    python_bin = "python.exe"
    core_modules = BaseFlavor.core_modules.union({"ntpath.py"})

    def python_bins(self, version_info):
        return [
            "{}.exe".format(i)
            for i in super(Flavor, self).python_bins(version_info)
        ]

    def lib_dir(self, version_info):
        return "Lib"

    @property
    def activation_scripts(self):
        return {"activate.bat", "activate.ps1", "deactivate.bat"}

    def execute(self, command, **env):
        # Windows needs a valid system root
        super(Flavor, self).execute(
            command, SYSTEMROOT=os.environ['SYSTEMROOT'], **env
        )


flavor = Flavor()
