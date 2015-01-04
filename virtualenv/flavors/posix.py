from virtualenv.flavors.base import BaseFlavor


class PosixFlavor(BaseFlavor):
    bin_dir = "bin"
    python_bin = "python"

    @property
    def activation_scripts(self):
        return {"activate.sh", "activate.fish", "activate.csh"}
