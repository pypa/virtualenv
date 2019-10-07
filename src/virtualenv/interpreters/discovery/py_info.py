"""
The PythonInfo contains information about a concrete instance of a Python interpreter

Note: this file is also used to query target interpreters, so can only use standard library methods
"""
from __future__ import absolute_import, print_function, unicode_literals

import copy
import json
import logging
import os
import platform
import subprocess
import sys
from collections import OrderedDict, namedtuple

IS_WIN = sys.platform == "win32"

VersionInfo = namedtuple("VersionInfo", ["major", "minor", "micro", "releaselevel", "serial"])


def _get_path_extensions():
    return list(OrderedDict.fromkeys([""] + os.environ.get("PATHEXT", "").lower().split(os.pathsep)))


EXTENSIONS = _get_path_extensions()


class PythonInfo(object):
    """Contains information for a Python interpreter"""

    def __init__(self):
        # qualifies the python
        self.platform = sys.platform
        self.implementation = platform.python_implementation()

        # this is a tuple in earlier, struct later, unify to our own named tuple
        self.version_info = VersionInfo(*list(sys.version_info))
        self.architecture = 64 if sys.maxsize > 2 ** 32 else 32

        self.executable = sys.executable  # executable we were called with
        self.original_executable = self.executable
        self.base_executable = getattr(sys, "_base_executable", None)  # some platforms may set this

        self.version = sys.version
        self.os = os.name

        # information about the prefix - determines python home
        self.prefix = getattr(sys, "prefix", None)  # prefix we think
        self.base_prefix = getattr(sys, "base_prefix", None)  # venv
        self.real_prefix = getattr(sys, "real_prefix", None)  # old virtualenv

        # information about the exec prefix - dynamic stdlib modules
        self.base_exec_prefix = getattr(sys, "base_exec_prefix", None)
        self.exec_prefix = getattr(sys, "exec_prefix", None)

        try:
            __import__("venv")
            has = True
        except ImportError:
            has = False
        self.has_venv = has
        self.path = sys.path

    @property
    def version_str(self):
        return ".".join(str(i) for i in self.version_info[0:3])

    @property
    def version_release_str(self):
        return ".".join(str(i) for i in self.version_info[0:2])

    @property
    def is_old_virtualenv(self):
        return self.real_prefix is not None

    @property
    def is_venv(self):
        return self.base_prefix is not None and self.version_info.major == 3

    def __repr__(self):
        return "PythonInfo({!r})".format(self.__dict__)

    def to_json(self):
        data = copy.deepcopy(self.__dict__)
        # noinspection PyProtectedMember
        data["version_info"] = data["version_info"]._asdict()  # namedtuple to dictionary
        return json.dumps(data, indent=2)

    @classmethod
    def from_json(cls, payload):
        data = json.loads(payload)
        data["version_info"] = VersionInfo(**data["version_info"])  # restore this to a named tuple structure
        info = copy.deepcopy(CURRENT)
        info.__dict__ = data
        return info

    @property
    def system_prefix(self):
        return self.real_prefix or self.base_prefix or self.prefix

    @property
    def system_exec_prefix(self):
        return self.real_prefix or self.base_exec_prefix or self.exec_prefix

    @property
    def system_executable(self):
        env_prefix = self.real_prefix or self.base_prefix
        if env_prefix:
            if self.real_prefix is None and self.base_executable is not None:
                return self.base_executable
            return self.find_exe(env_prefix)
        else:
            return self.executable

    def find_exe(self, home):
        # we don't know explicitly here, do some guess work - our executable name should tell
        exe_base_name = os.path.basename(self.executable)
        possible_names = self._find_possible_exe_names(exe_base_name)
        possible_folders = self._find_possible_folders(exe_base_name, home)
        for folder in possible_folders:
            for name in possible_names:
                candidate = os.path.join(folder, name)
                if os.path.exists(candidate):
                    return candidate
        what = "|".join(possible_names)  # pragma: no cover
        raise RuntimeError("failed to detect {} in {}".format(what, "|".join(possible_folders)))  # pragma: no cover

    def _find_possible_folders(self, exe_base_name, home):
        candidate_folder = OrderedDict()
        if self.executable.startswith(self.prefix):
            relative = self.executable[len(self.prefix) : -len(exe_base_name)]
            candidate_folder["{}{}".format(home, relative)] = None
        candidate_folder[home] = None
        return list(candidate_folder.keys())

    @staticmethod
    def _find_possible_exe_names(exe_base_name):
        exe_no_suffix = os.path.splitext(exe_base_name)[0]
        name_candidate = OrderedDict()
        for ext in EXTENSIONS:
            for at in range(3, -1, -1):
                cur_ver = sys.version_info[0:at]
                version = ".".join(str(i) for i in cur_ver)
                name = "{}{}{}".format(exe_no_suffix, version, ext)
                name_candidate[name] = None
        return list(name_candidate.keys())

    @classmethod
    def from_exe(cls, exe, raise_on_error=True):

        path = "{}.py".format(os.path.splitext(__file__)[0])
        cmd = [exe, path]
        # noinspection DuplicatedCode
        # this is duplicated here because this file is executed on its own, so cannot be refactored otherwise
        try:
            process = subprocess.Popen(
                cmd, universal_newlines=True, stdin=subprocess.PIPE, stderr=subprocess.PIPE, stdout=subprocess.PIPE
            )
            out, err = process.communicate()
            code = process.returncode
        except OSError as os_error:
            out, err, code = "", os_error.strerror, os_error.errno
        if code != 0:
            if raise_on_error:
                msg = "failed to query {} with code {}{}{}".format(
                    exe, code, " out: []".format(out) if out else "", " err: []".format(err) if err else ""
                )
                raise RuntimeError(msg)
            else:
                logging.debug("failed %s with code %s out %s err %s", cmd, code, out, err)
                return None

        result = cls.from_json(out)
        result.executable = exe  # keep original executable as this may contain initialization code
        return result

    def satisfies(self, spec, impl_must_match):
        """check if a given specification can be satisfied by the this python interpreter instance"""
        if self.executable == spec.path:  # if the path is a our own executable path we're done
            return True

        if spec.path is not None:  # if path set, and is not our original executable name, this does not match
            root, _ = os.path.splitext(os.path.basename(self.original_executable))
            if root != spec.path:
                return False

        if impl_must_match:
            if spec.implementation is not None and spec.implementation != self.implementation:
                return False

        if spec.architecture is not None and spec.architecture != self.architecture:
            return False

        for our, req in zip(self.version_info[0:3], (spec.major, spec.minor, spec.patch)):
            if req is not None and our is not None and our != req:
                return False
        return True


CURRENT = PythonInfo()

if __name__ == "__main__":
    print(CURRENT.to_json())
