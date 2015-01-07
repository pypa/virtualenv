from __future__ import absolute_import, division, print_function

import os
import subprocess


class BaseFlavor(object):

    def bootstrap_modules(self, base_python):
        return set([
            "__future__",
            "_abcoll",
            "_bootlocale",
            "_collections_abc",
            "_dummy_thread",
            "_weakrefset",
            "abc",
            "base64",
            "bisect",
            "codecs",
            "collections",
            "config",
            "config-{1}.{2}{0}".format(base_python["sys.abiflags"], *base_python["sys.version_info"][:2]),
            "copy",
            "copy_reg",
            "copyreg",
            "encodings",
            "fnmatch",
            "functools",
            "genericpath",
            "hashlib",
            "heapq",
            "hmac",
            "imp",
            "importlib",
            "io",
            "keyword",
            "lib-dynload",
            "linecache",
            "locale",
            "nt",
            "ntpath",
            "operator",
            "os",
            "plat-%s" % base_python["arch"],
            "posix",
            "posixpath",
            "random",
            "re",
            "readline",
            "reprlib"
            "rlcompleter",
            "shutil",
            "sre",
            "sre_compile",
            "sre_constants",
            "sre_parse",
            "stat",
            "struct",
            "tarfile",
            "tempfile",
            "token",
            "tokenize",
            "traceback",
            "types",
            "warnings",
            "weakref",
            "zlib",
            "UserDict",
        ])

    @property
    def activation_scripts(self):
        raise NotImplementedError

    def python_bins(self, base_python):
        raise NotImplementedError

    def lib_dir(self, base_python):
        raise NotImplementedError

    def execute(self, command, **env):
        # We want to copy the environment that we"re running in before
        # executing our command, this is because by specifying the env to our
        # subprocess call we break the ability to inherient the environment.
        real_env = os.environ.copy()
        real_env.update(env)

        subprocess.check_call(command, env=real_env)
