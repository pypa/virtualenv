"""
The PythonInfo contains information about a concrete instance of a Python interpreter

Note: this file is also used to query target interpreters, so can only use standard library methods
"""
from __future__ import absolute_import, print_function

import json
import logging
import os
import pipes
import platform
import re
import sys
import sysconfig
from collections import OrderedDict, namedtuple
from distutils.command.install import SCHEME_KEYS
from distutils.dist import Distribution

VersionInfo = namedtuple("VersionInfo", ["major", "minor", "micro", "releaselevel", "serial"])


def _get_path_extensions():
    return list(OrderedDict.fromkeys([""] + os.environ.get("PATHEXT", "").lower().split(os.pathsep)))


EXTENSIONS = _get_path_extensions()
_CONF_VAR_RE = re.compile(r"\{\w+\}")


class PythonInfo(object):
    """Contains information for a Python interpreter"""

    def __init__(self):
        def u(v):
            return v.decode("utf-8") if isinstance(v, bytes) else v

        # qualifies the python
        self.platform = u(sys.platform)
        self.implementation = u(platform.python_implementation())
        if self.implementation == "PyPy":
            self.pypy_version_info = tuple(u(i) for i in sys.pypy_version_info)

        # this is a tuple in earlier, struct later, unify to our own named tuple
        self.version_info = VersionInfo(*list(u(i) for i in sys.version_info))
        self.architecture = 64 if sys.maxsize > 2 ** 32 else 32

        self.executable = u(sys.executable)  # executable we were called with
        self.original_executable = u(self.executable)
        self.base_executable = u(getattr(sys, "_base_executable", None))  # some platforms may set this

        self.version = u(sys.version)
        self.os = u(os.name)

        # information about the prefix - determines python home
        self.prefix = u(getattr(sys, "prefix", None))  # prefix we think
        self.base_prefix = u(getattr(sys, "base_prefix", None))  # venv
        self.real_prefix = u(getattr(sys, "real_prefix", None))  # old virtualenv

        # information about the exec prefix - dynamic stdlib modules
        self.base_exec_prefix = u(getattr(sys, "base_exec_prefix", None))
        self.exec_prefix = u(getattr(sys, "exec_prefix", None))

        try:
            __import__("venv")
            has = True
        except ImportError:
            has = False
        self.has_venv = has
        self.path = [u(i) for i in sys.path]
        self.file_system_encoding = u(sys.getfilesystemencoding())
        self.stdout_encoding = u(getattr(sys.stdout, "encoding", None))

        self.sysconfig_paths = {u(i): u(sysconfig.get_path(i, expand=False)) for i in sysconfig.get_path_names()}
        config_var_keys = set()
        for element in self.sysconfig_paths.values():
            for k in _CONF_VAR_RE.findall(element):
                config_var_keys.add(u(k[1:-1]))
        self.sysconfig_config_vars = {u(i): u(sysconfig.get_config_var(i)) for i in config_var_keys}

        self.distutils_install = {u(k): u(v) for k, v in self._distutils_install().items()}

    def _distutils_install(self):
        # follow https://github.com/pypa/pip/blob/master/src/pip/_internal/locations.py#L95
        d = Distribution({"script_args": "--no-user-cfg"})
        d.parse_config_files()
        i = d.get_command_obj("install", create=True)
        i.prefix = "a"
        i.finalize_options()
        result = {key: (getattr(i, "install_{}".format(key))[1:]).lstrip(os.sep) for key in SCHEME_KEYS}
        return result

    @property
    def version_str(self):
        return ".".join(str(i) for i in self.version_info[0:3])

    @property
    def version_release_str(self):
        return ".".join(str(i) for i in self.version_info[0:2])

    @property
    def python_name(self):
        version_info = self.version_info
        return "python{}.{}".format(version_info.major, version_info.minor)

    @property
    def is_old_virtualenv(self):
        return self.real_prefix is not None

    @property
    def is_venv(self):
        return self.base_prefix is not None and self.version_info.major == 3

    def __unicode__(self):
        content = repr(self)
        if sys.version_info == 2:
            content = content.decode("utf-8")
        return content

    def __repr__(self):
        return "{}({!r})".format(self.__class__.__name__, self.__dict__)

    def __str__(self):
        content = "{}({})".format(
            self.__class__.__name__,
            ", ".join(
                "{}={}".format(k, v)
                for k, v in (
                    (
                        "spec",
                        "{}{}-{}".format(
                            self.implementation, ".".join(str(i) for i in self.version_info), self.architecture
                        ),
                    ),
                    ("exe", self.executable),
                    ("original" if self.original_executable != self.executable else None, self.original_executable),
                    (
                        "base"
                        if self.base_executable is not None and self.base_executable != self.executable
                        else None,
                        self.base_executable,
                    ),
                    ("platform", self.platform),
                    ("version", repr(self.version)),
                    ("encoding_fs_io", "{}-{}".format(self.file_system_encoding, self.stdout_encoding)),
                )
                if k is not None
            ),
        )
        return content

    def to_json(self):
        data = {var: getattr(self, var) for var in vars(self)}
        # noinspection PyProtectedMember
        data["version_info"] = data["version_info"]._asdict()  # namedtuple to dictionary
        return json.dumps(data, indent=2)

    @classmethod
    def from_json(cls, payload):
        data = json.loads(payload)
        data["version_info"] = VersionInfo(**data["version_info"])  # restore this to a named tuple structure
        result = cls()
        result.__dict__ = {k: v for k, v in data.items()}
        return result

    @property
    def system_prefix(self):
        return self.real_prefix or self.base_prefix or self.prefix

    @property
    def system_exec_prefix(self):
        return self.real_prefix or self.base_exec_prefix or self.exec_prefix

    @property
    def system_executable(self):
        env_prefix = self.real_prefix or self.base_prefix
        if env_prefix:  # if this is a virtual environment
            if self.real_prefix is None and self.base_executable is not None:  # use the saved host if present
                return self.base_executable
            # otherwise fallback to discovery mechanism
            return self.find_exe_based_of(inside_folder=env_prefix)
        else:
            # need original executable here, as if we need to copy we want to copy the interpreter itself, not the
            # setup script things may be wrapped up in
            return self.original_executable

    def find_exe_based_of(self, inside_folder):
        # we don't know explicitly here, do some guess work - our executable name should tell
        possible_names = self._find_possible_exe_names()
        possible_folders = self._find_possible_folders(inside_folder)
        for folder in possible_folders:
            for name in possible_names:
                candidate = os.path.join(folder, name)
                if os.path.exists(candidate):
                    info = PythonInfo.from_exe(candidate)
                    keys = {"implementation", "architecture", "version_info"}
                    if all(getattr(info, k) == getattr(self, k) for k in keys):
                        return candidate
        what = "|".join(possible_names)  # pragma: no cover
        raise RuntimeError("failed to detect {} in {}".format(what, "|".join(possible_folders)))  # pragma: no cover

    def _find_possible_folders(self, inside_folder):
        candidate_folder = OrderedDict()
        executables = OrderedDict()
        executables[self.executable] = None
        executables[self.original_executable] = None
        for exe in executables.keys():
            base = os.path.dirname(exe)
            # following path pattern of the current
            if base.startswith(self.prefix):
                relative = base[len(self.prefix) :]
                candidate_folder["{}{}".format(inside_folder, relative)] = None

        # or at root level
        candidate_folder[inside_folder] = None

        return list(candidate_folder.keys())

    def _find_possible_exe_names(self):
        name_candidate = OrderedDict()
        for name in self._possible_base():
            for at in (3, 2, 1, 0):
                version = ".".join(str(i) for i in self.version_info[:at])
                for arch in ["-{}".format(self.architecture), ""]:
                    for ext in EXTENSIONS:
                        candidate = "{}{}{}{}".format(name, version, arch, ext)
                        name_candidate[candidate] = None
        return list(name_candidate.keys())

    def _possible_base(self):
        possible_base = OrderedDict()
        possible_base[os.path.splitext(os.path.basename(self.executable))[0]] = None
        possible_base[self.implementation] = None
        # python is always the final option as in practice is used by multiple implementation as exe name
        if "python" in possible_base:
            del possible_base["python"]
        possible_base["python"] = None
        for base in possible_base:
            lower = base.lower()
            yield lower
            from virtualenv.info import is_fs_case_sensitive

            if is_fs_case_sensitive():
                if base != lower:
                    yield base
                upper = base.upper()
                if upper != base:
                    yield upper

    _cache_from_exe = {}

    @classmethod
    def clear_cache(cls):
        cls._cache_from_exe.clear()

    @classmethod
    def from_exe(cls, exe, raise_on_error=True):
        # this method is not used by itself, so here and called functions can import stuff locally
        key = os.path.realpath(exe)
        if key in cls._cache_from_exe:
            result, failure = cls._cache_from_exe[key]
        else:
            failure, result = cls._load_for_exe(exe)
            cls._cache_from_exe[key] = result, failure
        if failure is not None:
            if raise_on_error:
                raise failure
            else:
                logging.warning("%s", str(failure))
        return result

    @classmethod
    def _load_for_exe(cls, exe):
        from virtualenv.util.subprocess import subprocess, Popen

        cmd = cls._get_exe_cmd(exe)
        # noinspection DuplicatedCode
        # this is duplicated here because this file is executed on its own, so cannot be refactored otherwise
        logging.debug(u"get interpreter info via cmd: %s", Cmd(cmd))
        try:
            process = Popen(
                cmd, universal_newlines=True, stdin=subprocess.PIPE, stderr=subprocess.PIPE, stdout=subprocess.PIPE
            )
            out, err = process.communicate()
            code = process.returncode
        except OSError as os_error:
            out, err, code = "", os_error.strerror, os_error.errno
        result, failure = None, None
        if code == 0:
            result = cls.from_json(out)
            result.executable = exe  # keep original executable as this may contain initialization code
        else:
            msg = "failed to query {} with code {}{}{}".format(
                exe, code, " out: {!r}".format(out) if out else "", " err: {!r}".format(err) if err else ""
            )
            failure = RuntimeError(msg)
        return failure, result

    @classmethod
    def _get_exe_cmd(cls, exe):
        cmd = [exe, "-s"]
        from virtualenv.info import IS_ZIPAPP

        self_path = os.path.abspath(__file__)
        if IS_ZIPAPP:
            from virtualenv.util.zipapp import extract_to_app_data
            from virtualenv.util.path import Path

            path = str(extract_to_app_data(Path(self_path)))
        else:
            path = "{}.py".format(os.path.splitext(self_path)[0])
        cmd.append(path)
        return cmd

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

    def sysconfig_path(self, key, config_var=None, sep=os.sep):
        pattern = self.sysconfig_paths[key]
        if config_var is None:
            config_var = self.sysconfig_config_vars
        else:
            base = {k: v for k, v in self.sysconfig_config_vars.items()}
            base.update(config_var)
            config_var = base
        return pattern.format(**config_var).replace(u"/", sep)


class Cmd(object):
    def __init__(self, cmd, env=None):
        self.cmd = cmd
        self.env = env

    def __repr__(self):
        def e(v):
            return v.decode("utf-8") if isinstance(v, bytes) else v

        cmd_repr = e(" ").join(pipes.quote(e(c)) for c in self.cmd)
        if self.env is not None:
            cmd_repr += e(" env of {!r}").format(self.env)
        return cmd_repr


CURRENT = PythonInfo()

if __name__ == "__main__":
    print(CURRENT.to_json())
