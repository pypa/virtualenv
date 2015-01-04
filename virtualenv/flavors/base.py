import os
import subprocess


class BaseFlavor(object):
    core_modules = {
        "posixpath.py", "stat.py", "genericpath.py", "warnings.py",
        "linecache.py", "types.py", "UserDict.py", "_abcoll.py", "abc.py",
        "_weakrefset.py", "copy_reg.py",
    }

    def python_bins(self, version_info):
        return [
            "python{}".format(".".join(map(str, version_info[:i])))
            for i in range(3)
        ]

    def lib_dir(self, version_info):
        return os.path.join(
            "lib",
            "python{}".format(
                ".".join(map(str, version_info[:2]))
            ),
        )

    def execute(self, command, **env):
        subprocess.check_call(command, env=env)
