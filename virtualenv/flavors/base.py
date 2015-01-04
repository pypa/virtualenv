from __future__ import absolute_import, division, print_function

import os
import subprocess


class BaseFlavor(object):

    core_modules = set([
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

    def globalsitepaths(self, prefix):
        raise NotImplementedError

    def execute(self, command, **env):
        # We want to copy the environment that we're running in before
        # executing our command, this is because by specifying the env to our
        # subprocess call we break the ability to inherient the environment.
        real_env = os.environ.copy()
        real_env.update(env)

        subprocess.check_call(command, env=real_env)


