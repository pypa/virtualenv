from __future__ import absolute_import, print_function, unicode_literals

import json
import logging
import os
import shutil
from abc import abstractmethod

from pathlib2 import Path

from virtualenv.config.options import RunOption
from virtualenv.error import ProcessCallFailed
from virtualenv.info import IS_WIN
from virtualenv.seed.link_app_data import bootstrap as bootstrap_via_link_app_data
from virtualenv.util import copy, ensure_dir, run_cmd, symlink

HERE = Path(__file__).absolute().parent
DEBUG_SCRIPT = HERE / "debug.py"


class Creator(object):
    def __init__(self, options, interpreter):
        self.options = options
        self.interpreter = interpreter
        self.copier = symlink if self.options.symlinks else copy
        self._debug = None
        self._seed_packages = bootstrap_via_link_app_data

    # noinspection PyUnusedLocal
    @staticmethod
    def default_options(interpreter):
        return RunOption()

    @staticmethod
    def extend_parser(parser, options, interpreter):
        pass

    @abstractmethod
    def setup_python(self):
        """setup an isolated build environment for the target interpreter without any seed packages"""

    def run(self):
        if self.options.no_venv is False and self.interpreter.has_venv:
            self.create_using_host()
            # this should also create the configuration
        else:
            # else:
            # 1. setup virtual environment skeleton directory
            # 2. setup python
            # 3. create pyvenv configuration
            if self.env_dir.exists() and self.options.clear:
                shutil.rmtree(str(self.env_dir))
            for directory in self.ensure_directories():
                ensure_dir(directory)
            self.create_configuration()
            true_system_site = self.options.system_site
            try:
                self.options.system_site = False
                self.setup_python()
                if not self.options.without_pip:
                    logging.debug("seed starting packages with %r", self._seed_packages)
                    self._seed_packages(self)
            finally:
                if true_system_site != self.options.system_site:
                    self.options.system_site = true_system_site
                    self.create_configuration()

    def create_using_host(self):
        """
        The lazy mans approach, if the target interpreter already contains venv, delegate the job to that.
        """
        cmd = self.get_host_create_cmd()
        logging.info("create with venv %s", " ".join(cmd))
        code, out, err = run_cmd(cmd)
        if code != 0:
            raise ProcessCallFailed(code, out, err, cmd)

    def get_host_create_cmd(self):
        cmd = [str(self.interpreter.system_executable), "-m", "venv", "--without-pip"]
        if self.options.system_site:
            cmd.append("--system-site-packages")
        if self.options.prompt is not None:
            version = self.interpreter.version_info
            if version.major > 2 and version.minor > 5:
                # 3.6 added first the prompt flag in venv
                cmd.extend(["--prompt", self.options.prompt])
        if self.options.clear is True:
            cmd.append("--clear")
        cmd.append(self.options.dest_dir)
        return cmd

    def ensure_directories(self):
        directories = [self.env_dir, self.bin_dir]
        directories.extend(self.site_packages)
        directories.append(self.pyvenv_path.parent)
        return directories

    def config_data(self):
        result = {
            "home": self.interpreter.system_exec_prefix,
            "include-system-site-packages": "true" if self.options.system_site else "false",
            "implementation": self.interpreter.implementation,
        }
        if self.options.prompt is not None:
            result["prompt"] = self.prompt
        return result

    def create_configuration(self):
        """
        Create a configuration file indicating where the environment's Python was copied from, and whether the system
        site-packages should be made available in the environment.
        """
        with open(str(self.pyvenv_path), "wt") as file_handler:
            logging.info("write %s", self.pyvenv_path)
            for key, value in self.config_data().items():
                line = "{} = {}".format(key, value)
                logging.debug("\t%s", line)
                file_handler.write(line)
                file_handler.write("\n")

    @property
    def pyvenv_path(self):
        return self.env_dir / "pyvenv.cfg"

    @property
    def env_dir(self):
        return Path(self.options.dest_dir)

    @property
    def env_name(self):
        return self.env_dir.parts[-1]

    @property
    def bin_name(self):
        raise NotImplementedError

    @property
    def bin_dir(self):
        return self.env_dir / self.bin_name

    @property
    def prompt(self):
        return self.options.prompt or self.env_name

    @property
    def lib_dir(self):
        raise NotImplementedError

    @property
    def site_packages(self):
        return [self.lib_dir / "site-packages"]

    @property
    def python_name(self):
        version_info = self.interpreter.version_info
        return "python{}.{}".format(version_info.major, version_info.minor)

    @property
    def env_exe(self):
        return self.bin_dir / "python{}".format(".exe" if IS_WIN else "")

    @property
    def debug(self):
        if self._debug is None:
            self._debug = get_env_debug_info(self.env_exe, self.debug_script())
        return self._debug

    # noinspection PyMethodMayBeStatic
    def debug_script(self):
        return DEBUG_SCRIPT


def get_env_debug_info(env_exe, debug_script):
    cmd = [str(env_exe), str(debug_script)]
    logging.debug(" ".join(cmd))
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
