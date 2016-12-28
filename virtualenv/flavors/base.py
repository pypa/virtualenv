from __future__ import absolute_import, division, print_function

import os
import subprocess


class BaseFlavor(object):

    def core_modules(self, base_python):
        return set([
            # Files
            "posixpath.py", "stat.py", "genericpath.py", "warnings.py",
            "linecache.py", "types.py", "UserDict.py", "_abcoll.py", "abc.py",
            "_weakrefset.py", "copy_reg.py",
        ])

    @property
    def activation_scripts(self):
        raise NotImplementedError

    def python_bins(self, version_info):
        raise NotImplementedError

    def lib_dir(self, version_info):
        raise NotImplementedError

    def globalsitepaths(self, base_python):
        raise NotImplementedError

    def execute(self, command, **env):
        # We want to copy the environment that we're running in before
        # executing our command, this is because by specifying the env to our
        # subprocess call we break the ability to inherient the environment.
        subprocess.check_call(command, env=dict(os.environ, **env))
