from __future__ import absolute_import, print_function, unicode_literals

import json
import logging
import os
import shutil
import sys
from abc import ABCMeta, abstractmethod
from argparse import ArgumentTypeError

import six
from six import add_metaclass

from virtualenv.info import IS_WIN
from virtualenv.pyenv_cfg import PyEnvCfg
from virtualenv.util import Path, run_cmd
from virtualenv.version import __version__

HERE = Path(__file__).absolute().parent
DEBUG_SCRIPT = HERE / "debug.py"


@add_metaclass(ABCMeta)
class Creator(object):
    def __init__(self, options, interpreter):
        self.interpreter = interpreter
        self._debug = None
        self.dest_dir = Path(options.dest_dir)
        self.system_site_package = options.system_site
        self.clear = options.clear
        self.pyenv_cfg = PyEnvCfg.from_folder(self.dest_dir)

    @classmethod
    def add_parser_arguments(cls, parser, interpreter):
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
            help="Give the virtual environment access to the system site-packages dir.",
        )

        def validate_dest_dir(raw_value):
            """No path separator in the path and must be write-able"""
            if os.pathsep in raw_value:
                raise ArgumentTypeError(
                    "destination {!r} must not contain the path separator ({}) as this would break "
                    "the activation scripts".format(raw_value, os.pathsep)
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
                    if os.access(str(dest), os.W_OK):
                        break
                    else:
                        non_write_able(dest, value)
                base, _ = dest.parent, dest.name
                if base == dest:
                    non_write_able(dest, value)  # pragma: no cover
                dest = base
            return str(value)

        def non_write_able(dest, value):
            common = Path(*os.path.commonprefix([value.parts, dest.parts]))
            raise ArgumentTypeError(
                "the destination {} is not write-able at {}".format(dest.relative_to(common), common)
            )

        parser.add_argument(
            "dest_dir", help="directory to create virtualenv at", type=validate_dest_dir, default="env", nargs="?",
        )

    def run(self):
        if self.dest_dir.exists() and self.clear:
            shutil.rmtree(str(self.dest_dir), ignore_errors=True)
        self.create()
        self.set_pyenv_cfg()

    @abstractmethod
    def create(self):
        raise NotImplementedError

    @classmethod
    def supports(cls, interpreter):
        raise NotImplementedError

    def set_pyenv_cfg(self):
        self.pyenv_cfg.content = {
            "home": self.interpreter.system_exec_prefix,
            "include-system-site-packages": "true" if self.system_site_package else "false",
            "implementation": self.interpreter.implementation,
            "virtualenv": __version__,
        }

    @property
    def env_name(self):
        return six.ensure_text(self.dest_dir.parts[-1])

    @property
    def bin_name(self):
        raise NotImplementedError

    @property
    def bin_dir(self):
        return self.dest_dir / self.bin_name

    @property
    def lib_dir(self):
        raise NotImplementedError

    @property
    def site_packages(self):
        return [self.lib_dir / "site-packages"]

    @property
    def exe(self):
        return self.bin_dir / "python{}".format(".exe" if IS_WIN else "")

    @property
    def debug(self):
        if self._debug is None:
            self._debug = get_env_debug_info(self.exe, self.debug_script())
        return self._debug

    # noinspection PyMethodMayBeStatic
    def debug_script(self):
        return DEBUG_SCRIPT


def get_env_debug_info(env_exe, debug_script):
    cmd = [str(env_exe), str(debug_script)]
    logging.debug(" ".join(six.ensure_text(i) for i in cmd))
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    code, out, err = run_cmd(cmd)
    # noinspection PyBroadException
    try:
        if code != 0:
            result = eval(out)
        else:
            result = json.loads(out)
        if err:
            result["err"] = err
    except Exception as exception:
        return {"out": out, "err": err, "returncode": code, "exception": repr(exception)}
    if "sys" in result and "path" in result["sys"]:
        del result["sys"]["path"][0]
    return result
