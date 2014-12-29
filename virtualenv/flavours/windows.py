class Flavour(object):

    @property
    def activation_scripts(self):
        return {"activate.bat", "activate.ps1", "deactivate.bat"}

flavour = Flavour()
