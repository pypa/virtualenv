from __future__ import absolute_import, unicode_literals

import logging
import os

from pathlib2 import Path

from virtualenv.info import PY3, get_default_config_dir

from .convert import convert

try:
    import ConfigParser
except ImportError:
    # noinspection PyPep8Naming
    import configparser as ConfigParser


DEFAULT_CONFIG_FILE = get_default_config_dir() / "virtualenv.ini"


class IniConfig(object):
    VIRTUALENV_CONFIG_FILE_ENV_VAR = "VIRTUALENV_CONFIG_FILE"
    STATE = {None: "failed to parse", True: "active", False: "missing"}

    section = "virtualenv"

    def __init__(self):
        config_file = os.environ.get(self.VIRTUALENV_CONFIG_FILE_ENV_VAR, None)
        self.is_env_var = config_file is not None
        self.config_file = Path(config_file) if config_file is not None else DEFAULT_CONFIG_FILE
        self._cache = {}

        self.has_config_file = self.config_file.exists()
        if self.has_config_file:
            self.config_file = self.config_file.resolve()
            self.config_parser = ConfigParser.ConfigParser()
            try:
                with self.config_file.open("rt") as file_handler:
                    reader = getattr(self.config_parser, "read_file" if PY3 else "readfp")
                    reader(file_handler)
                self.has_virtualenv_section = self.config_parser.has_section(self.section)
            except Exception as exception:
                logging.error("failed to read config file %s because %r", config_file, exception)
                self.has_config_file = None

    def get(self, key, as_type):
        cache_key = key, as_type
        if cache_key in self._cache:
            result = self._cache[cache_key]
        else:
            # noinspection PyBroadException
            try:
                source = "file"
                raw_value = self.config_parser.get(self.section, key.lower())
                value = convert(raw_value, as_type, source)
                result = value, source
            except Exception:
                result = None
        self._cache[cache_key] = result
        return result

    def __bool__(self):
        return bool(self.has_config_file) and bool(self.has_virtualenv_section)

    @property
    def epilog(self):
        msg = "{}config file {} {} (change{} via env var {})"
        return msg.format(
            os.linesep,
            self.config_file,
            self.STATE[self.has_config_file],
            "d" if self.is_env_var else "",
            self.VIRTUALENV_CONFIG_FILE_ENV_VAR,
        )
