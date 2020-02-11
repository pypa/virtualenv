"""
The PythonInfo contains information about a concrete instance of a Python interpreter

Note: this file is also used to query target interpreters, so can only use standard library methods
"""
from __future__ import absolute_import, print_function

import json
import logging
import os
import platform
import re
import sys
import sysconfig
from collections import OrderedDict, namedtuple
from distutils.command.install import SCHEME_KEYS
from distutils.dist import Distribution
from string import digits

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

        self.version = u(sys.version)
        self.os = u(os.name)

        # information about the prefix - determines python home
        self.prefix = u(getattr(sys, "prefix", None))  # prefix we think
        self.base_prefix = u(getattr(sys, "base_prefix", None))  # venv
        self.real_prefix = u(getattr(sys, "real_prefix", None))  # old virtualenv

        # information about the exec prefix - dynamic stdlib modules
        self.base_exec_prefix = u(getattr(sys, "base_exec_prefix", None))
        self.exec_prefix = u(getattr(sys, "exec_prefix", None))

        self.executable = u(sys.executable)  # the executable we were invoked via
        self.original_executable = u(self.executable)  # the executable as known by the interpreter
        self.system_executable = self._fast_get_system_executable()  # the executable we are based of (if available)

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

        self.sysconfig_vars = {u(i): u(sysconfig.get_config_var(i)) for i in config_var_keys}
        if self.implementation == "PyPy" and sys.version_info.major == 2:
            self.sysconfig_vars[u"implementation_lower"] = u"python"

        self.distutils_install = {u(k): u(v) for k, v in self._distutils_install().items()}
        self.system_stdlib = self.sysconfig_path(
            "stdlib",
            {k: (self.system_prefix if v.startswith(self.prefix) else v) for k, v in self.sysconfig_vars.items()},
        )
        self._creators = None

    def _fast_get_system_executable(self):
        """Try to get the system executable by just looking at properties"""
        if self.real_prefix or (
            self.base_prefix is not None and self.base_prefix != self.prefix
        ):  # if this is a virtual environment
            if self.real_prefix is None:
                base_executable = getattr(sys, "_base_executable", None)  # some platforms may set this to help us
                if base_executable is not None:  # use the saved system executable if present
                    if sys.executable != base_executable:  # we know we're in a virtual environment, cannot be us
                        return base_executable
            return None  # in this case we just can't tell easily without poking around FS and calling them, bail
        # if we're not in a virtual environment, this is already a system python, so return the original executable
        # note we must choose the original and not the pure executable as shim scripts might throw us off
        return self.original_executable

    @staticmethod
    def _distutils_install():
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

    def sysconfig_path(self, key, config_var=None, sep=os.sep):
        pattern = self.sysconfig_paths[key]
        if config_var is None:
            config_var = self.sysconfig_vars
        else:
            base = {k: v for k, v in self.sysconfig_vars.items()}
            base.update(config_var)
            config_var = base
        return pattern.format(**config_var).replace(u"/", sep)

    def creators(self, refresh=False):
        if self._creators is None or refresh is True:
            from virtualenv.run.plugin.creators import CreatorSelector

            self._creators = CreatorSelector.for_interpreter(self)
        return self._creators

    @property
    def system_include(self):
        return self.sysconfig_path(
            "include",
            {k: (self.system_prefix if v.startswith(self.prefix) else v) for k, v in self.sysconfig_vars.items()},
        )

    @property
    def system_prefix(self):
        return self.real_prefix or self.base_prefix or self.prefix

    @property
    def system_exec_prefix(self):
        return self.real_prefix or self.base_exec_prefix or self.exec_prefix

    def __unicode__(self):
        content = repr(self)
        if sys.version_info == 2:
            content = content.decode("utf-8")
        return content

    def __repr__(self):
        return "{}({!r})".format(
            self.__class__.__name__, {k: v for k, v in self.__dict__.items() if not k.startswith("_")}
        )

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
                    (
                        "system"
                        if self.system_executable is not None and self.system_executable != self.executable
                        else None,
                        self.system_executable,
                    ),
                    (
                        "original"
                        if (
                            self.original_executable != self.system_executable
                            and self.original_executable != self.executable
                        )
                        else None,
                        self.original_executable,
                    ),
                    ("exe", self.executable),
                    ("platform", self.platform),
                    ("version", repr(self.version)),
                    ("encoding_fs_io", "{}-{}".format(self.file_system_encoding, self.stdout_encoding)),
                )
                if k is not None
            ),
        )
        return content

    @classmethod
    def clear_cache(cls):
        # this method is not used by itself, so here and called functions can import stuff locally
        from virtualenv.discovery.cached_py_info import clear

        clear()
        cls._cache_exe_discovery.clear()

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

        for our, req in zip(self.version_info[0:3], (spec.major, spec.minor, spec.micro)):
            if req is not None and our is not None and our != req:
                return False
        return True

    _current_system = None
    _current = None

    @classmethod
    def current(cls):
        """
        This locates the current host interpreter information. This might be different than what we run into in case
        the host python has been upgraded from underneath us.
        """
        if cls._current is None:
            cls._current = cls.from_exe(sys.executable, raise_on_error=True, resolve_to_host=False)
        return cls._current

    @classmethod
    def current_system(cls):
        """
        This locates the current host interpreter information. This might be different than what we run into in case
        the host python has been upgraded from underneath us.
        """
        if cls._current_system is None:
            cls._current_system = cls.from_exe(sys.executable, raise_on_error=True, resolve_to_host=True)
        return cls._current_system

    def _to_json(self):
        # don't save calculated paths, as these are non primitive types
        return json.dumps(self._to_dict(), indent=2)

    def _to_dict(self):
        data = {var: (getattr(self, var) if var not in ("_creators",) else None) for var in vars(self)}
        # noinspection PyProtectedMember
        data["version_info"] = data["version_info"]._asdict()  # namedtuple to dictionary
        return data

    @classmethod
    def from_exe(cls, exe, raise_on_error=True, ignore_cache=False, resolve_to_host=True):
        """Given a path to an executable get the python information"""
        # this method is not used by itself, so here and called functions can import stuff locally
        from virtualenv.discovery.cached_py_info import from_exe

        proposed = from_exe(cls, exe, raise_on_error=raise_on_error, ignore_cache=ignore_cache)
        # noinspection PyProtectedMember
        if isinstance(proposed, PythonInfo) and resolve_to_host:
            proposed = proposed._resolve_to_system(proposed)
        return proposed

    @classmethod
    def _from_json(cls, payload):
        # the dictionary unroll here is to protect against pypy bug of interpreter crashing
        raw = json.loads(payload)
        return cls._from_dict({k: v for k, v in raw.items()})

    @classmethod
    def _from_dict(cls, data):
        data["version_info"] = VersionInfo(**data["version_info"])  # restore this to a named tuple structure
        result = cls()
        result.__dict__ = {k: v for k, v in data.items()}
        return result

    @classmethod
    def _resolve_to_system(cls, target):
        start_executable = target.executable
        prefixes = OrderedDict()
        while target.system_executable is None:
            prefix = target.real_prefix or target.base_prefix or target.prefix
            if prefix in prefixes:
                for at, (p, t) in enumerate(prefixes.items(), start=1):
                    logging.error("%d: prefix=%s, info=%r", at, p, t)
                logging.error("%d: prefix=%s, info=%r", len(prefixes) + 1, prefix, target)
                raise RuntimeError("prefixes are causing a circle {}".format("|".join(prefixes.keys())))
            prefixes[prefix] = target
            target = target.discover_exe(prefix=prefix, exact=False)

        if target.executable != target.system_executable:
            target = cls.from_exe(target.system_executable)
        target.executable = start_executable
        return target

    _cache_exe_discovery = {}

    def discover_exe(self, prefix, exact=True):
        key = prefix, exact
        if key in self._cache_exe_discovery and prefix:
            logging.debug("discover exe cache %r via %r", key, self._cache_exe_discovery[key])
            return self._cache_exe_discovery[key]
        logging.debug("discover system for %s in %s", self, prefix)
        # we don't know explicitly here, do some guess work - our executable name should tell
        possible_names = self._find_possible_exe_names()
        possible_folders = self._find_possible_folders(prefix)
        discovered = []
        for folder in possible_folders:
            for name in possible_names:
                exe_path = os.path.join(folder, name)
                if os.path.exists(exe_path):
                    info = self.from_exe(exe_path, resolve_to_host=False, raise_on_error=False)
                    if info is None:  # ignore if for some reason we can't query
                        continue
                    for item in ["implementation", "architecture", "version_info"]:
                        found = getattr(info, item)
                        searched = getattr(self, item)
                        if found != searched:
                            if item == "version_info":
                                found, searched = ".".join(str(i) for i in found), ".".join(str(i) for i in searched)
                            logging.debug(
                                "refused interpreter %s because %s differs %s != %s",
                                info.executable,
                                item,
                                found,
                                searched,
                            )
                            if exact is False:
                                discovered.append(info)
                            break
                    else:
                        self._cache_exe_discovery[key] = info
                        return info
        if exact is False and discovered:
            info = self._select_most_likely(discovered, self)
            logging.debug(
                "no exact match found, chosen most similar of %s within base folders %s",
                info,
                os.pathsep.join(possible_folders),
            )
            self._cache_exe_discovery[key] = info
            return info
        what = "|".join(possible_names)  # pragma: no cover
        raise RuntimeError(
            "failed to detect {} in {}".format(what, os.pathsep.join(possible_folders))
        )  # pragma: no cover

    @staticmethod
    def _select_most_likely(discovered, target):
        # no exact match found, start relaxing our requirements then to facilitate system package upgrades that
        # could cause this (when using copy strategy of the host python)
        def sort_by(info):
            # we need to setup some priority of traits, this is as follows:
            # implementation, major, minor, micro, architecture, tag, serial
            matches = [
                info.implementation == target.implementation,
                info.version_info.major == target.version_info.major,
                info.version_info.minor == target.version_info.minor,
                info.architecture == target.architecture,
                info.version_info.micro == target.version_info.micro,
                info.version_info.releaselevel == target.version_info.releaselevel,
                info.version_info.serial == target.version_info.serial,
            ]
            priority = sum((1 << pos if match else 0) for pos, match in enumerate(reversed(matches)))
            return priority

        sorted_discovered = sorted(discovered, key=sort_by, reverse=True)  # sort by priority in decreasing order
        most_likely = sorted_discovered[0]
        return most_likely

    def _find_possible_folders(self, inside_folder):
        candidate_folder = OrderedDict()
        executables = OrderedDict()
        executables[os.path.realpath(self.executable)] = None
        executables[self.executable] = None
        executables[os.path.realpath(self.original_executable)] = None
        executables[self.original_executable] = None
        for exe in executables.keys():
            base = os.path.dirname(exe)
            # following path pattern of the current
            if base.startswith(self.prefix):
                relative = base[len(self.prefix) :]
                candidate_folder["{}{}".format(inside_folder, relative)] = None

        # or at root level
        candidate_folder[inside_folder] = None
        if self.executable.startswith(self.prefix):
            binary_within = os.path.relpath(os.path.dirname(self.executable), self.prefix)
            candidate_folder[os.path.join(inside_folder, binary_within)] = None

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
        basename = os.path.splitext(os.path.basename(self.executable))[0].rstrip(digits)
        possible_base[basename] = None
        possible_base[self.implementation] = None
        # python is always the final option as in practice is used by multiple implementation as exe name
        if "python" in possible_base:
            del possible_base["python"]
        possible_base["python"] = None
        for base in possible_base:
            lower = base.lower()
            yield lower
            from virtualenv.info import fs_is_case_sensitive

            if fs_is_case_sensitive():
                if base != lower:
                    yield base
                upper = base.upper()
                if upper != base:
                    yield upper


if __name__ == "__main__":
    # dump a JSON representation of the current python
    # noinspection PyProtectedMember
    print(PythonInfo()._to_json())
