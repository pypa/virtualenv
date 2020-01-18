from __future__ import absolute_import, print_function, unicode_literals

import json
import logging
import os
import shutil
import sys
from abc import ABCMeta, abstractmethod
from argparse import ArgumentTypeError
from ast import literal_eval
from collections import OrderedDict
from stat import S_IWUSR

import six
from six import add_metaclass

from virtualenv.info import IS_ZIPAPP
from virtualenv.interpreters.discovery.py_info import Cmd
from virtualenv.pyenv_cfg import PyEnvCfg
from virtualenv.util.path import Path
from virtualenv.util.subprocess import run_cmd
from virtualenv.util.zipapp import extract_to_app_data
from virtualenv.version import __version__

HERE = Path(__file__).absolute().parent
DEBUG_SCRIPT = HERE / "debug.py"


@add_metaclass(ABCMeta)
class Creator(object):
    def __init__(self, options, interpreter):
        self.interpreter = interpreter
        self._debug = None
        self.dest_dir = Path(options.dest_dir)
        self.enable_system_site_package = options.system_site
        self.clear = options.clear
        self.pyenv_cfg = PyEnvCfg.from_folder(self.dest_dir)

        self._stdlib = None
        self._system_stdlib = None
        self._conf_vars = None

    @property
    def bin_dir(self):
        return self.script_dir

    @property
    def script_dir(self):
        return self.dest_dir / Path(self.interpreter.distutils_install["scripts"])

    @property
    def purelib(self):
        return self.dest_dir / self.interpreter.distutils_install["purelib"]

    @property
    def platlib(self):
        return self.dest_dir / self.interpreter.distutils_install["platlib"]

    @property
    def libs(self):
        return list(OrderedDict(((self.platlib, None), (self.purelib, None))).keys())

    @property
    def stdlib(self):
        if self._stdlib is None:
            self._stdlib = Path(self.interpreter.sysconfig_path("stdlib", config_var=self._config_vars))
        return self._stdlib

    @property
    def system_stdlib(self):
        if self._system_stdlib is None:
            conf_vars = self._calc_config_vars(self.interpreter.system_prefix)
            self._system_stdlib = Path(self.interpreter.sysconfig_path("stdlib", conf_vars))
        return self._system_stdlib

    @property
    def _config_vars(self):
        if self._conf_vars is None:
            self._conf_vars = self._calc_config_vars(six.ensure_text(str(self.dest_dir)))
        return self._conf_vars

    def _calc_config_vars(self, to):
        return {
            k: (to if v.startswith(self.interpreter.prefix) else v)
            for k, v in self.interpreter.sysconfig_config_vars.items()
        }

    def __repr__(self):
        return six.ensure_str(self.__unicode__())

    def __unicode__(self):
        return "{}({})".format(self.__class__.__name__, ", ".join("{}={}".format(k, v) for k, v in self._args()))

    def _args(self):
        return [
            ("dest", six.ensure_text(str(self.dest_dir))),
            ("global", self.enable_system_site_package),
            ("clear", self.clear),
        ]

    @classmethod
    def add_parser_arguments(cls, parser, interpreter):
        parser.add_argument(
            "dest_dir", help="directory to create virtualenv at", type=cls.validate_dest_dir, default="venv", nargs="?",
        )
        parser.add_argument(
            "--clear",
            dest="clear",
            action="store_true",
            help="clear out the non-root install and start from scratch",
            default=False,
        )
        parser.add_argument(
            "--system-site-packages",
            default=False,
            action="store_true",
            dest="system_site",
            help="give the virtual environment access to the system site-packages dir",
        )

    @classmethod
    def validate_dest_dir(cls, raw_value):
        """No path separator in the path, valid chars and must be write-able"""

        def non_write_able(dest, value):
            common = Path(*os.path.commonprefix([value.parts, dest.parts]))
            raise ArgumentTypeError(
                "the destination {} is not write-able at {}".format(dest.relative_to(common), common)
            )

        # the file system must be able to encode
        # note in newer CPython this is always utf-8 https://www.python.org/dev/peps/pep-0529/
        encoding = sys.getfilesystemencoding()
        refused = OrderedDict()
        kwargs = {"errors": "ignore"} if encoding != "mbcs" else {}
        for char in six.ensure_text(raw_value):
            try:
                trip = char.encode(encoding, **kwargs).decode(encoding)
                if trip == char:
                    continue
                raise ValueError(trip)
            except ValueError:
                refused[char] = None
        if refused:
            raise ArgumentTypeError(
                "the file system codec ({}) cannot handle characters {!r} within {!r}".format(
                    encoding, "".join(refused.keys()), raw_value
                )
            )
        for char in (i for i in (os.pathsep, os.altsep) if i is not None):
            if char in raw_value:
                raise ArgumentTypeError(
                    "destination {!r} must not contain the path separator ({}) as this would break "
                    "the activation scripts".format(raw_value, char)
                )

        value = Path(raw_value)
        if value.exists() and value.is_file():
            raise ArgumentTypeError("the destination {} already exists and is a file".format(value))
        if (3, 3) <= sys.version_info <= (3, 6):
            # pre 3.6 resolve is always strict, aka must exists, sidestep by using os.path operation
            dest = Path(os.path.realpath(raw_value))
        else:
            dest = value.resolve()
        value = dest
        while dest:
            if dest.exists():
                if os.access(six.ensure_text(str(dest)), os.W_OK):
                    break
                else:
                    non_write_able(dest, value)
            base, _ = dest.parent, dest.name
            if base == dest:
                non_write_able(dest, value)  # pragma: no cover
            dest = base
        return str(value)

    def run(self):
        if self.dest_dir.exists() and self.clear:
            logging.debug("delete %s", self.dest_dir)

            def onerror(func, path, exc_info):
                if not os.access(path, os.W_OK):
                    os.chmod(path, S_IWUSR)
                    func(path)
                else:
                    raise

            shutil.rmtree(str(self.dest_dir), ignore_errors=True, onerror=onerror)
        self.create()
        self.set_pyenv_cfg()

    @abstractmethod
    def create(self):
        raise NotImplementedError

    @classmethod
    def supports(cls, interpreter):
        return True

    def set_pyenv_cfg(self):
        self.pyenv_cfg.content = {
            "home": self.interpreter.system_exec_prefix,
            "include-system-site-packages": "true" if self.enable_system_site_package else "false",
            "implementation": self.interpreter.implementation,
            "version_info": ".".join(str(i) for i in self.interpreter.version_info),
            "virtualenv": __version__,
        }

    @property
    def env_name(self):
        return six.ensure_text(self.dest_dir.parts[-1])

    @property
    def debug(self):
        if self._debug is None and self.exe is not None:
            self._debug = get_env_debug_info(self.exe, self.debug_script())
        return self._debug

    # noinspection PyMethodMayBeStatic
    def debug_script(self):
        return DEBUG_SCRIPT

    @property
    def exe(self):
        return None


def get_env_debug_info(env_exe, debug_script):
    if IS_ZIPAPP:
        debug_script = extract_to_app_data(debug_script)
    cmd = [six.ensure_text(str(env_exe)), six.ensure_text(str(debug_script))]
    logging.debug("debug via %r", Cmd(cmd))
    env = os.environ.copy()
    env.pop(str("PYTHONPATH"), None)
    code, out, err = run_cmd(cmd)
    # noinspection PyBroadException
    try:
        if code != 0:
            result = literal_eval(out)
        else:
            result = json.loads(out)
        if err:
            result["err"] = err
    except Exception as exception:
        return {"out": out, "err": err, "returncode": code, "exception": repr(exception)}
    if "sys" in result and "path" in result["sys"]:
        del result["sys"]["path"][0]
    return result
