import subprocess


class BaseFlavor(object):

    core_modules = {
        "posixpath.py", "stat.py", "genericpath.py", "warnings.py",
        "linecache.py", "types.py", "UserDict.py", "_abcoll.py", "abc.py",
        "_weakrefset.py", "copy_reg.py",
    }

    @property
    def activation_scripts(self):
        raise NotImplementedError

    def python_bins(self, version_info):
        raise NotImplementedError

    def lib_dir(self, version_info):
        raise NotImplementedError

    def execute(self, command, **env):
        subprocess.check_call(command, env=env)
