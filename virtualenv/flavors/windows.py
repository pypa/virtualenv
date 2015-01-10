from __future__ import absolute_import, division, print_function

from virtualenv.flavors.base import BaseFlavor


class WindowsFlavor(BaseFlavor):

    def bin_dir(self, python_info):
        if python_info["is_pypy"]:
            return "bin"
        else:
            return "Scripts"

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

    def extra_bins(self, python_info):
        if python_info["is_pypy"]:
            return [
                'libexpat.dll',
                'libpypy.dll',
                'libpypy-c.dll',
                'libeay32.dll',
                'ssleay32.dll',
                'sqlite3.dll',
                'tcl85.dll',
                'tk85.dll'
            ]
        else:
            return []

    def lib_dir(self, python_info):
        return "Lib"

    def include_dir(self, python_info):
        return "include"
