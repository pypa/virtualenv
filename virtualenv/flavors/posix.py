from __future__ import absolute_import, division, print_function

import posixpath

from virtualenv.flavors.base import BaseFlavor


class PosixFlavor(BaseFlavor):

    bin_dir = "bin"
    python_bin = "python"

    @property
    def activation_scripts(self):
        return set(["activate.sh", "activate.fish", "activate.csh"])

    def python_bins(self, version_info):
        return [
            "python%s" % ".".join(map(str, version_info[:i]))
            for i in range(3)
        ]

    def globalsitepaths(self, base_python):
        prefix = base_python["sys.prefix"]
        version_info = base_python["sys.version_info"]
        is_64bit = base_python["is_64bit"]
        arch = base_python["arch"]

        paths = [os.path.join(prefix, "lib", "python%s.%s" % version_info[:2])]
        lib64_path = os.path.join(prefix, "lib64", "python%s.%s" % version_info[:2])
        if os.path.exists(lib64_path):
            if is_64bit:
                paths.insert(0, lib64_path)
            else:
                paths.append(lib64_path)

        plat_path = os.path.join(prefix, "lib", "python%s.%s" % version_info[:2], "plat-%s" % arch)
        if os.path.exists(plat_path):
            paths.append(plat_path)

        return paths

    def lib_dir(self, version_info):
        return posixpath.join(
            "lib",
            "python{0}".format(
                ".".join(map(str, version_info[:2]))
            ),
        )
