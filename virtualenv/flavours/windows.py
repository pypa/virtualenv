from virtualenv.flavours.base import BaseFlavour


class Flavour(BaseFlavour):
    bin_dir = "Scripts"
    python_bin = "python.exe"

    def python_bins(self, version_info):
        return ["{}.exe".format(i) for i in super(Flavour, self).python_bins(version_info)]

    @property
    def activation_scripts(self):
        return {"activate.bat", "activate.ps1", "deactivate.bat"}

flavour = Flavour()
