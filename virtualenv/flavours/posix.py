from virtualenv.flavours.base import BaseFlavour


class Flavour(BaseFlavour):
    bin_dir = "bin"
    python_bin = "python"

    @property
    def activation_scripts(self):
        return {"activate.sh", "activate.fish", "activate.csh"}

flavour = Flavour()
