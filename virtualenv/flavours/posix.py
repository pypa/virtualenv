class Flavour(object):

    @property
    def activation_scripts(self):
        return {"activate.sh", "activate.fish", "activate.csh"}

flavour = Flavour()
