from __future__ import annotations

import logging
import os
from configparser import ConfigParser, Error
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar, Final

from platformdirs import user_config_dir

from .convert import convert

if TYPE_CHECKING:
    from collections.abc import Mapping
    from typing import Any

    from .convert import TypeData

_LOGGER: Final[logging.Logger] = logging.getLogger(__name__)


class IniConfig:
    """The ``virtualenv`` section of the config file, found through the environment or the default location.

    :param env: the environment variables, ``None`` for the process environment

    :var VIRTUALENV_CONFIG_FILE_ENV_VAR: the environment variable naming the config file
    :var STATE: the description of the config file state for each state value
    :var section: the name of the section read from the config file
    :var is_env_var: ``True`` when the config file was named by the environment variable
    :var config_file: the path of the config file
    :var has_config_file: whether the config file exists and was read
    :var has_virtualenv_section: whether the config file has a ``virtualenv`` section
    :var config_parser: the parser of the config file

    """

    VIRTUALENV_CONFIG_FILE_ENV_VAR: ClassVar[str] = "VIRTUALENV_CONFIG_FILE"
    STATE: ClassVar[dict[bool | None, str]] = {None: "failed to parse", True: "active", False: "missing"}

    section = "virtualenv"

    def __init__(self, env: Mapping[str, str] | None = None) -> None:
        env = os.environ if env is None else env
        # an empty value counts as unset, as it does for the VIRTUALENV_<OPTION> variables, instead of naming the cwd
        config_file = env.get(self.VIRTUALENV_CONFIG_FILE_ENV_VAR) or None
        self.is_env_var = config_file is not None
        if config_file is None:
            config_file = Path(user_config_dir(appname="virtualenv", appauthor="pypa")) / "virtualenv.ini"
        else:
            config_file = Path(config_file)
        self.config_file = config_file
        self._cache = {}

        self.has_config_file: bool | None = None
        self.has_virtualenv_section = False
        # no interpolation: values are literal, as env vars and flags are, so a % in a prompt or path survives
        self.config_parser: Final[ConfigParser] = ConfigParser(interpolation=None)
        exception = None
        try:
            self.has_config_file = self.config_file.exists()
            if self.has_config_file:
                self.config_file = self.config_file.resolve()
                self._load()
                self.has_virtualenv_section = self.config_parser.has_section(self.section)
        except (OSError, UnicodeError, Error) as exc:
            self.has_config_file = None
            exception = exc
        if exception is not None:
            _LOGGER.error("failed to read config file %s because %r", config_file, exception)

    def _load(self) -> None:
        with self.config_file.open("rt", encoding="utf-8-sig") as file_handler:
            return self.config_parser.read_file(file_handler)

    def __bool__(self) -> bool:
        return bool(self.has_config_file) and bool(self.has_virtualenv_section)

    @property
    def epilog(self) -> str:
        """The help text line that describes the config file and whether it is active."""
        return (
            f"\nconfig file {self.config_file} {self.STATE[self.has_config_file]} "
            f"(change{'d' if self.is_env_var else ''} via env var {self.VIRTUALENV_CONFIG_FILE_ENV_VAR})"
        )

    def get(
        self, key: str, as_type: TypeData
    ) -> tuple[Any, str] | None:  # simplint: ignore[imprecise-annotation]  # type known at run time
        """Return the value of a key from the config file, reading the file once.

        :param key: the option name
        :param as_type: the converter to apply to the value

        :returns: the converted value and the source it came from, ``None`` when the key is not set

        """
        cache_key = key, as_type
        if cache_key in self._cache:
            return self._cache[cache_key]
        try:
            raw_value = self.config_parser.get(self.section, key.lower())
            source = "file"
            result = convert(raw_value, as_type, source), source
        # a value that fails conversion reads as unset instead of failing the run
        except Exception:  # ruff:ignore[blind-except]
            result = None
        self._cache[cache_key] = result
        return result


__all__ = [
    "IniConfig",
]
