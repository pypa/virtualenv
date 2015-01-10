from __future__ import absolute_import, division, print_function

import os
import subprocess


class BaseFlavor(object):

    def bootstrap_modules(self, python_info):
        return set([
            "UserDict",
            "__future__",
            "_abcoll",
            "_bootlocale",
            "_collections_abc",
            "_dummy_thread",
            "_functools",
            "_weakrefset",
            "_struct",
            "abc",
            "atexit",
            "base64",
            "bisect",
            "codecs",
            "collections",
            "config",
            "config-{1}.{2}{0}".format(python_info["sys.abiflags"], *python_info["sys.version_info"][:2]),
            "contextlib",
            "copy",
            "copy_reg",
            "copyreg",
            "encodings",
            "errors",
            "fnmatch",
            "functools",
            "genericpath",
            "glob",
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
            "logging",
            "nt",
            "ntpath",
            "operator",
            "optparse",
            "pickle",
            "pkgutil",
            "plat-%s" % python_info["arch"],
            "posix",
            "posixpath",
            "random",
            "re",
            "readline",
            "reprlib"
            "rlcompleter",
            "runpy",
            "shutil",
            "sre",
            "sre_compile",
            "sre_constants",
            "sre_parse",
            "stat",
            "string",
            "struct",
            "subprocess",
            "tarfile",
            "tempfile",
            "textwrap",
            "token",
            "tokenize",
            "traceback",
            "types",
            "warnings",
            "weakref",
            "zipfile",
            "zlib",
        ])

    @property
    def activation_scripts(self):
        raise NotImplementedError

    def python_bins(self, python_info):
        raise NotImplementedError

    def lib_dir(self, python_info):
        raise NotImplementedError

    def execute(self, command, **env):
        # We want to copy the environment that we"re running in before
        # executing our command, this is because by specifying the env to our
        # subprocess call we break the ability to inherient the environment.
        real_env = os.environ.copy()
        real_env.update(env)

        subprocess.check_call(command, env=real_env)
